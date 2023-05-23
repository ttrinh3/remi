from remi.gui import *    
import remi.gui as gui
from remi import start, App
import RPi.GPIO as GPIO
import os
import signal
import numpy as np
import time
from datetime import datetime
import datetime
import schedule
import serial
from weatherbit.api import Api
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from csv import writer
import io
import random
import socket
#test

import email, smtplib, ssl
from providers import PROVIDERS
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return str(IP)

currentip = get_ip()

def send_sms_via_email(
    number: str,
    message: str,
    provider: str,
    sender_credentials: tuple,
    subject: str = "Login to UI with:",
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 465,
):
    sender_email, email_password = sender_credentials
    receiver_email = f'{number}@{PROVIDERS.get(provider).get("sms")}'

    email_message = f"Subject:{subject}\nTo:{receiver_email}\n{message}"

    with smtplib.SMTP_SSL(
        smtp_server, smtp_port, context=ssl.create_default_context()
    ) as email:
        email.login(sender_email, email_password)
        email.sendmail(sender_email, receiver_email, email_message)


number = "abcd" #put greg's phone number here

provider = "T-Mobile" #put his provider here

#sender_credentials = ("CSUFArboretum@gmail.com", "MBjX^tQ}H7>S7?@z") #don't change this
sender_credentials = ("abcd", "abcd") #don't change this




#array to contain data for the graph.
button_size = "1%" #parameter to control all button sizes
graphdata = np.zeros((33,30), dtype=int)#33 sensor values because some sensors are combo sensors
button_top = 1

class MatplotImage(gui.Image):
    ax = None

    def __init__(self, **kwargs):
        super(MatplotImage, self).__init__("/%s/get_image_data?update_index=0" % id(self), **kwargs)
        self._buf = None
        self._buflock = threading.Lock()

        self._fig = Figure(figsize=(10,10))
        self.ax = self._fig.add_subplot(111)

        self.redraw()

    def redraw(self):
        canv = FigureCanvasAgg(self._fig)
        buf = io.BytesIO()
        canv.print_figure(buf, format='png')
        with self._buflock:
            if self._buf is not None:
                self._buf.close()
            self._buf = buf

        i = int(time.time() * 1e6)
        self.attributes['src'] = "/%s/get_image_data?update_index=%d" % (id(self), i)

        super(MatplotImage, self).redraw()

    def get_image_data(self, update_index):
        with self._buflock:
            if self._buf is None:
                return None
            self._buf.seek(0)
            data = self._buf.read()

        return [data, {'Content-type': 'image/png'}]
        

smart_duration = np.zeros(shape=(5,2))#variable that stores the smart durations

smart_schedule_flag = False

from csv import writer
file_index=0
today = datetime.datetime.today().weekday()
files=[]
for i in range(30):
    files.append("file"+str(i)+".csv")

def weatherAPI_pull(): #returns info of next 7 days of weather info in array: 1.) temperature, precipitation rate, date/time
    api_key = "abcd"
    api = Api(api_key)
    api.set_granularity('daily')
    forecast = api.get_forecast(city="Fullerton,CA")
    a = forecast.get_series(['temp','precip'])
    # print(a[0]['temp']) # a[0] means today a[1] is tmrw
    # print(a[0]['precip']) # rate of precip
    
    # make tuple to store full week
    # 'a' stores dictionary of information for next 16 days
    # NOTE: time records midnight of each day (00:00) in (HR:MIN) format
    
    #[{'temp': 14.3, 'precip': 1.64887, 'datetime': datetime.datetime(2022, 3, 4, 0, 0)}, {'temp': 11.7, 'precip': 0, 'datetime': datetime.datetime(2022, 3, 5, 0, 0)}...]
    temp_array = []
    for i in range(0,7):
        #only saves 7 days' information 
        temp_array.append(a[i])
    return temp_array


#do hostname -I to get ip address then place the ip address at the bottom
#flags that are global so that threads can be deactivated by any function
thread_1_alive = True #thread1 this thread creates the rows dynamically.
thread_2_alive = True #this thread constantly processes the water FIFO
thread_3_alive = True#this thread checks whether the current time conditions match the user input schedule

#define sprinkler pins here. For example Sprinkler=14 for pin 14
SprinklerGPIOs=[14,15,18,23,24]#gpios are in order of rows. meaning 14 is row1
#sensor_table=[]
a = Container()
days_pressed=[]#going to store boolean values of which days of the week are pressed, monday is first ends on sunday
GPIO.setmode(GPIO.BCM)
for i in SprinklerGPIOs:
    GPIO.setup(i,GPIO.OUT)
water_FIFO=[] #this will contain queue of solenoids that need to be on
enabled=False
stoppressed=False
durationed=False
matchingtimes= False
mailbox = 0 #simple global variable for exec commands (used in save())
schedule_button_pressed = False
bool_gray=False # this is to flip the color layers every row
row_top_amount=[]#this is used to find top% amoutns
total_children=[]#to contain all the elements on the page
row_top_amount_index=0 #this is used in conjunction with row_top_amount
addrowbuttonpressed=False
for i in range(25):
    row_top_amount.append(str(i*1.3)+"%") #25 different levels for each layer#off set by placing the top inside the string
row_number=5

import time
from threading import Thread

def checknonsensevalues(x):
    try: 
        if (int(x)<0): #if x is int-able, it's negative and return 0
            return 0
        else:
            return int(x) #if x is int-able and not negative, then legit value
                
    except: #if above doens't work, that means it's a string and return 0 as well
        return 0


    # all given as strings
def timesplitter(start, end, interval): # this now returns a bool whether the current time matches the interval times.
    
    #strings of time are interpreted in military time 
    #interval units in minutes (keep variable/dynamic)
    
    
    #                       1PM  3PM  10 minute intervals
    # EXAMPLE: timesplitter(1300,1500,10)
   
    #                        0 0  : 0 0
    #military time split by hours : minutes, where hours range from 0-23
    # and minutes range from 0 - 59
    
    # Do error cases
    start_hours = []
    interval = checknonsensevalues(interval)
    if (len(start)!=4 or len(end)!= 4 or interval==0 or int(start)>=int(end) ):
        
        return 'error'
        
    for i in range(0,len(start),2):
        start_hours.append(int(start[i:i+2]))


    # start_hours now include hours in first index and minutes in second index as int
    
    end_hours = []
    for j in range(0,len(end),2):
        end_hours.append(int(end[j:j+2]))
    # end_hours now include hours in first index and minutes in second index
    
    # handles bad inputs for either hours or minutes
    if(start_hours[0] < 0 or start_hours[0] > 23 or end_hours[0] < 0 or end_hours[0] > 23 or start_hours[1] > 59 or start_hours[1] < 0 or end_hours[1] > 59 or end_hours[1] < 0 or len(start)!=4 or len(end)!=4):
        print("wrong schedule input")
        return 'error'
    
    # calculates total time in mintues
    
    difference_in_hours = end_hours[0] - start_hours[0]
    difference_in_minutes = end_hours[1] - start_hours[1]
    
    
    # convert hours to minutes
    total_time_in_minutes = (60*difference_in_hours)+(difference_in_minutes)
    
    
    
    # time_array will hold all the times to check
    time_array = []
    
    # append start time
    time_array.append(start)
   
    amount_of_watering = total_time_in_minutes/int(interval)
   
    for i in range(0,int(amount_of_watering)):
        
        reference_time = time_array[i]
             
        
        new_time = str(int(reference_time) + int(interval)); #adding the interval
        
        while(len(new_time)!=4):
            new_time="0"+new_time
        
        if(int(new_time[-2]) > 5): #if tenths in the minutes,#you need to check 2 positions from the endnot from front
            new_time = int(new_time)
            new_time -= 60 #regroup minutes to hours
            new_time += 100
            new_time  = str(new_time)
            while (len(str(new_time))<4):
                new_time="0"+new_time
            time_array.append(str(new_time))
        else:
            time_array.append(str(new_time))
        #     if (len(str(new_time))<4):
        #         time_array.append('0' + str(new_time))
        #     else:
        #         time_array.append(str(new_time))
        # else:
        #     if (int(new_time)<1000):
        #         time_array.append('0'+str(new_time))
        #     else:
        #         time_array.append(str(new_time))
    t = time.localtime()
    hours = t.tm_hour
    minutes = t.tm_min
    hours = str(hours)
    minutes = str(minutes)
    target='abc'
    if (len(hours)<2):
        hours= '0'+hours
    if (len(minutes)<2):
        minutes= '0' + minutes
    target = hours + minutes
    print(f"The times to water are: {time_array} and target is: {target}")
    for lp in time_array:
        if (lp==target): #is time NOW equal to any of the splittings
            return True
    return False



class WaterControl(App):
    def __init__(self, *args):
        res_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'res')
        super(WaterControl, self).__init__(*args)
        
        




    def main(self):
        global graphdata
        maincontainer = Container() #this container defines the large white box
        maincontainer.attr_class = "Container"
        maincontainer.attr_editor_newclass = False
        maincontainer.css_background_color = "rgb(255,255,255)"
        maincontainer.css_height = "300%"
        maincontainer.css_left = "0%"
        maincontainer.css_position = "absolute"
        maincontainer.css_top = "0%"
        maincontainer.css_width = "100%"
        maincontainer.variable_name = "maincontainer"
                
        
        def create_checkbox(self,element, text, top,left,container):
            a = top
            b = left
            c= container
            exec(f'self.{element}=CheckBox()')
            exec(f'self.{element}.attr_class = "checkbox"')
            exec(f'self.{element}.attr_editor_newclass = False')
            exec(f'self.{element}.css_height = "1%"')
            exec(f'self.{element}.css_left = left')
            exec(f'self.{element}.css_position="absolute"')

            exec(f'self.{element}.css_top = top')
            exec(f'self.{element}.css_width = "0%"')

            exec(f'self.{element}.css_color = "rgb(0,0,0)"')
            exec(f'container.append(self.{element},"self.{element}")')
            
        def create_input(self,element, text, top,left,container):
            exec(f'self.{element}=Input(default_value=text)')
            exec(f'self.{element}.attr_class = "Input"')
            exec(f'self.{element}.attr_editor_newclass = False')
            exec(f'self.{element}.css_font_size = "" #have to use px for this')
            exec(f'self.{element}.css_height = "0.5%"')
            exec(f'self.{element}.css_left = left')
            exec(f'self.{element}.css_position="absolute"')
            exec(f'self.{element}.css_text_align = "center"')
            exec(f'self.{element}.css_top = top #increasing top, lowers position')
            exec(f'self.{element}.css_width = "5%"')
            exec(f'self.{element}.css_font_family="times new roman"')
            exec(f'self.{element}.css_color = "rgb(0,0,0)"')
            exec(f'container.append(self.{element},"self.{element}")')

        def create_label(self,element, text, top,left,container):
            exec(f'self.{element}=Label(default_value=text)')
            exec(f'self.{element}.attr_class = "Label"')
            exec(f'self.{element}.attr_editor_newclass = False')
            exec(f'self.{element}.css_font_size = "15px" ')
            exec(f'self.{element}.css_height = "5%"')
            exec(f'self.{element}.css_left = left')
            exec(f'self.{element}.css_position="absolute"')
            exec(f'self.{element}.css_text_align = "center"')
            exec(f'self.{element}.css_top = top')
            exec(f'self.{element}.css_width = "5%"')
            exec(f'self.{element}.css_font_family="times new roman"')
            exec(f'self.{element}.text=text')
            exec(f'self.{element}.css_color = "rgb(0,0,0)"')
            exec(f'container.append(self.{element},"self.{element}")')

        def create_container(self,element,color,top,container):

            exec(f'self.{element} = Container()#this contains the box for sprinkler elements')
            exec(f'self.{element}.attr_class = "Container"')
            exec(f'self.{element}.attr_editor_newclass = False')
            exec(f'self.{element}.css_background_color = color ')
            exec(f'self.{element}.css_height = "1.2%"')
            exec(f'self.{element}.css_left = "0%"')
            exec(f'self.{element}.css_position = "absolute"')
            exec(f'self.{element}.css_top = top')
            exec(f'self.{element}.css_width = "100%"')
            exec(f'self.{element}.variable_name = "self.{element}"')
          
            exec(f'container.append(self.{element},"self.{element}")')
 
                        

        def create_row(element,top,text):
            a=maincontainer
            global bool_gray
            bool_gray=not bool_gray# automatic color flipping every time create row is used.
            if (bool_gray):
                color = "rgb(211,211,211)"
            else:
                color = "rgb(255,255,255"

            create_container(self, element+"_subcontainer",color,top,a) #creates a layer and by this i mean color
            create_checkbox( self,element+"_EnableCheckbox","",top,"0%",a)#checkbox for enable
            create_label(self,element+"_RowLabel",text,top,"2%",a)#label for the row
            create_checkbox( self,element+"_MonCheckbox","",top,"7%",a) #checkbox for monday
            create_label(self,element+"_MonLabel","Monday",top,"9%",a)#label for tuesday

            create_checkbox( self,element+"_TuesCheckbox","",top,"14%",a) 
            create_label(self,element+"_TuesLabel","Tuesday",top,"16%",a)

            create_checkbox( self,element+"_WedCheckbox","",top,"21%",a) 
            create_label(self,element+"_WedLabel","Wednesday",top,"24%",a)

            create_checkbox( self,element+"_ThursCheckbox","",top,"30%",a) 
            create_label(self,element+"_ThursLabel","Thursday",top,"32.5%",a)

            create_checkbox( self,element+"_FriCheckbox","",top,"38%",a) 
            create_label(self,element+"_FriLabel","Friday",top,"40%",a)

            create_checkbox( self,element+"_SatCheckbox","",top,"44%",a) 
            create_label(self,element+"_SatLabel","Saturday",top,"46.5%",a)

            create_checkbox( self,element+"_SunCheckbox","",top,"51%",a) 
            create_label(self,element+"_SunLabel","Sunday",top,"53%",a)

            create_label(self,element+"_StartLabel","Start:",top,"58%",a)
            create_input(self,element+"_StartInput","",top,"62%",a)

            create_label(self,element+"_EndLabel","End:",top,"67%",a)
            create_input(self,element+"_EndInput","",top,"71%",a)

            create_label(self,element+"_IntervalLabel","Interval:",top,"77%",a)
            create_input(self,element+"_IntervalInput","",top,"82%",a)

            create_label(self,element+"_DurationLabel","Duration:",top,"88%",a)
            create_input(self,element+"_DurationInput","",top,"93%",a)





        #the top of each row and the top of each container should increase by the same amount
        #ATTENTION: whatever you add here, DELETE IT FROM THE TOTAL CHILDREN LIST both in create row and right below these elements
        global button_size
        button_size = "98%"
        border_radius = "8px" #how much to round the corners

        lis=[]
        for i in range(16):
            lis.append("a"+str(i))
        for i in range(16):
            lis.append("b"+str(i))  
        self.dropDown = gui.DropDown.new_from_list((lis))
        self.dropDown.attr_class = "button"
        self.dropDown.attr_editor_newclass = False
        self.dropDown.css_background_color = "rgb(240,240,240)"
        self.dropDown.css_height = "1.5%"
        self.dropDown.css_right = "45%"
        self.dropDown.css_position = "absolute"
        self.dropDown.css_top = "67%"
        self.dropDown.css_width = "5%"
        self.dropDown.variable_name = "bt"
        self.dropDown.text="Graph"
        self.dropDown.onchange(self.graph_function)
        maincontainer.append(self.dropDown,"self.dropDown")

        
        self.mpl = MatplotImage()
        self.mpl.style['margin'] = '10px'
        self.mpl.ax.set_title("test")
        self.mpl.ax.plot(graphdata[0])
        self.mpl.redraw()

        self.mpl.css_height = "30%"
        self.mpl.css_left = "25%"
        self.mpl.css_position = "absolute"
        self.mpl.css_bottom = "0%"
        self.mpl.css_width = "50%"
        self.mpl.variable_name = "image"

        maincontainer.append(self.mpl,"self.mpl")
        
        global button_top
        button_top = 5*1.3

        self.btcontainer = HBox() #this container defines the large white box
        self.btcontainer.attr_class = "Container"
        self.btcontainer.attr_editor_newclass = False
        self.btcontainer.css_background_color = "rgb(173,216,230)"
        self.btcontainer.css_height = "1.5%"
        self.btcontainer.css_left = "0%"
        self.btcontainer.css_position = "absolute"
        self.btcontainer.css_top = f"{button_top}%"
        self.btcontainer.css_width = "100%"
        self.btcontainer.variable_name = "btcontainer"
        maincontainer.append(self.btcontainer,"self.btcontainer")

        
        
        
        graphbt = Button() 
        graphbt.attr_class = "button"
        graphbt.attr_editor_newclass = False
        graphbt.css_background_color = "rgb(84,245,66)"
        graphbt.css_height = button_size
        graphbt.css_left = "20%"
        graphbt.css_position = "absolute"
        graphbt.css_top = "60%"
        graphbt.css_width = "5%"
        graphbt.css_border_radius = border_radius
        graphbt.css_color = "rgb(0,0,0)"

        graphbt.variable_name = "bt"
        graphbt.text="Graph"
        graphbt.onclick.do(self.graph_function)        
        
        self.btcontainer.append(graphbt,"graphbt")
        
        
        addrow = Button() 
        addrow.attr_class = "button"
        addrow.attr_editor_newclass = False
        addrow.css_background_color = "rgb(84,245,66)"
        addrow.css_height = button_size
        addrow.css_right = "50%"
        addrow.css_position = "absolute"
        addrow.css_top = "60%"
        addrow.css_width = "5%"
        addrow.variable_name = "addrow"
        addrow.text="Add Row"
        addrow.css_border_radius = border_radius
        addrow.onclick.do(self.confirm_create_row)
        self.btcontainer.append(addrow,"addrow")

        deleterow = Button() 
        deleterow.attr_class = "button"
        deleterow.attr_editor_newclass = False
        deleterow.css_background_color = "rgb(84,245,66)"
        deleterow.css_height = button_size
        deleterow.css_right = "60%"
        deleterow.css_position = "absolute"
        deleterow.css_top = "60%"
        deleterow.css_width = "5%"
        deleterow.variable_name = "deleterow"
        deleterow.text="Delete Row"
        deleterow.css_border_radius = border_radius
        deleterow.onclick.do(self.delete_row)
        self.btcontainer.append(deleterow,"deleterow")

        RunOnceButton = Button() 
        RunOnceButton.attr_class = "button"
        RunOnceButton.attr_editor_newclass = False
        RunOnceButton.css_background_color = "rgb(84,245,66)"
        RunOnceButton.css_height = button_size
        RunOnceButton.css_right = "40%"
        RunOnceButton.css_position = "absolute"
        RunOnceButton.css_top = "60%"
        RunOnceButton.css_width = "5%"
        RunOnceButton.variable_name = "RunOnceButton"
        RunOnceButton.text="Run Once"
        RunOnceButton.onclick.do(self.confirm_run_once)
        RunOnceButton.css_border_radius = border_radius
        self.btcontainer.append(RunOnceButton,"RunOnceButton")
        
        StopButton = Button() 
        StopButton.attr_class = "button"
        StopButton.attr_editor_newclass = False
        StopButton.css_background_color = "rgb(255,0,0)"
        StopButton.css_height = button_size
        StopButton.css_right = "30%"
        StopButton.css_position = "absolute"
        StopButton.css_top = "60%"
        StopButton.css_width = "5%"
        StopButton.variable_name = "StopButton"
        StopButton.text="STOP"
        StopButton.onclick.do(self.stop)
        StopButton.css_border_radius = border_radius
        self.btcontainer.append(StopButton,"StopButton")
        
        ScheduleButton = Button() 
        ScheduleButton.attr_class = "button"
        ScheduleButton.attr_editor_newclass = False
        ScheduleButton.css_background_color = "rgb(255,0,0)"
        ScheduleButton.css_height = button_size
        ScheduleButton.css_right = "20%"
        ScheduleButton.css_position = "absolute"
        ScheduleButton.css_top = "60%"
        ScheduleButton.css_width = "7%"
        ScheduleButton.css_border_radius = border_radius
        ScheduleButton.variable_name = "ScheduleButton"
        ScheduleButton.text="Run Scheduled"
        
        ScheduleButton.onclick.do(self.confirm_schedule)#uncomment this for regular schedule function
        self.btcontainer.append(ScheduleButton,"ScheduleButton")
        
        SmartScheduleButton = Button() 
        SmartScheduleButton.attr_class = "button"
        SmartScheduleButton.attr_editor_newclass = False
        SmartScheduleButton.css_background_color = "rgb(255,0,0)"
        SmartScheduleButton.css_height = button_size
        SmartScheduleButton.css_right = "0%"
        SmartScheduleButton.css_position = "absolute"
        SmartScheduleButton.css_top = "60%"
        SmartScheduleButton.css_width = "7%"
        SmartScheduleButton.variable_name = "SmartScheduleButton"
        SmartScheduleButton.text="Smart Schedule"
        SmartScheduleButton.onclick.do(self.confirm_smart_schedule)
        SmartScheduleButton.css_border_radius = border_radius
        self.btcontainer.append(SmartScheduleButton,"SmartScheduleButton")
        
        SensorButton = Button() 
        SensorButton.attr_class = "button"
        SensorButton.attr_editor_newclass = False
        SensorButton.css_background_color = "rgb(138,123,143)"
        SensorButton.css_height = button_size
        SensorButton.css_right = "10%"
        SensorButton.css_position = "absolute"
        SensorButton.css_top = "60%"
        SensorButton.css_width = "7%"
        SensorButton.variable_name = "SensorButton"
        SensorButton.text="Display Sensors"
        SensorButton.onclick.do(self.GrabSensorValues)
        SensorButton.css_border_radius = border_radius
        self.btcontainer.append(SensorButton,"SensorButton")
        
        download = Button() 
        download.attr_class = "button"
        download.attr_editor_newclass = False
        download.css_background_color = "rgb(138,123,143)"
        download.css_height = button_size
        download.css_left = "0%"
        download.css_position = "absolute"
        download.css_top = "60%"
        download.css_width = "5%"
        download.variable_name = "download"
        download.text="Download"
        download.css_border_radius = border_radius
        download.onclick.do(self.open_fileselection_dialog)
        self.btcontainer.append(download,"download")

        Reboot = Button()
        Reboot.css_border_radius = border_radius 
        Reboot.attr_class = "button"
        Reboot.attr_editor_newclass = False
        Reboot.css_background_color = "rgb(138,123,143)"
        Reboot.css_height = button_size
        Reboot.css_left = "10%"
        Reboot.css_position = "absolute"
        Reboot.css_top = "60%"
        Reboot.css_width = "5%"
        Reboot.variable_name = "Reboot"
        Reboot.text="Reboot"
        Reboot.onclick.do(self.Reboot)
        Reboot.css_border_radius = border_radius
        self.btcontainer.append(Reboot,"Reboot")
        

       
        
        #first 5 rows are created for the user
        global row_top_amount_index
        create_row("row1",row_top_amount[row_top_amount_index],"Row 1")#in the future exec this line but increase each number
        row_top_amount_index+=1
        create_row("row2",row_top_amount[row_top_amount_index],"Row 2")#everytime a new row is created, row number should be increased, percentage should be increased by 2
        row_top_amount_index+=1
        create_row("row3",row_top_amount[row_top_amount_index],"Row 3")
        row_top_amount_index+=1
        create_row("row4",row_top_amount[row_top_amount_index],"Row 4")
        row_top_amount_index+=1
        create_row("row5",row_top_amount[row_top_amount_index],"Row 5")
        #whenever the add row button is pressed create another row

        #_____FIRST THREAD_________# creates new rows when needed
        def thread_func(): 
            global row_number
            global addrowbuttonpressed
            global row_top_amount_index
            global thread_1_alive
            global currentip
            global number
            global provider
            global sender_credentials
            while (True and thread_1_alive):
                if (currentip!=get_ip()): #it means it got changed
                    currentip = get_ip() #update the currentip and send the new ip to user
                    send_sms_via_email(number, currentip, provider, sender_credentials)
                    
                schedule.run_pending()#this is actually for the third "thread" i just needed to place it somehwere that is in a loop
                if (addrowbuttonpressed):
                    row_number+=1
                    row_top_amount_index+=1
                    create_row("row"+str(row_top_amount_index+1),row_top_amount[row_top_amount_index],"Row "+str(row_top_amount_index+1))
                    
                    addrowbuttonpressed=False


        thread1=threading.Thread(target=thread_func) #this thread takes care of creating rows.
        thread1.start()
        #______SECOND THREAD__________# processes watering requests in the FIFO
        def watering_func():
            global water_FIFO
            global thread_2_alive
            global stoppressed
            while (True and thread_2_alive):#while thread is allowed to live
                
                while(len(water_FIFO)>=2 and len(water_FIFO)%2==0):#while there is something in the fifo queue
                    gpio=water_FIFO[0]
                    duration=water_FIFO[1]
                    del water_FIFO[0]
                    del water_FIFO[0]
                    start = time.time()
                    while (time.time()<start+int(duration) and stoppressed==False and thread_2_alive):#if input is minute, multiply duration by 60
                        GPIO.output(gpio,1)#turn on for the duration
                    GPIO.output(gpio,0)#turn off
                    print(f'after: {water_FIFO}')
                    
            
        thread2=threading.Thread(target=watering_func)
        thread2.start()
        
        
        global total_children

        total_children=[]
        for i in vars(maincontainer)['children']:
            total_children.append(i)#this contains all elements of the page
        #ATTENTION: YOU MUST DELETE ANYTHING THAT IS NOT PART OF THE ROWS BELOW THIS LINE
        #AND DO THE SAMETHING IN CREATE ROW
        
        # total_children.remove('deleterow') #delete the delete row button
        # total_children.remove('addrow') #delete the addrow button
        # total_children.remove('RunOnceButton') #delete the run once button
        # total_children.remove('StopButton')
        # total_children.remove("ScheduleButton")
        # total_children.remove("SensorButton")
        # total_children.remove("SmartScheduleButton")
        # total_children.remove('download')
        # total_children.remove('graphbt')
        total_children.remove("self.dropDown")
        total_children.remove("self.mpl")
        # total_children.remove("Reboot")
        total_children.remove("self.btcontainer")
        
        
        total_children=np.array(total_children)       
        total_children = np.reshape(total_children,(1+row_top_amount_index,25)) #everything was in one long list, now i'm making it 2d: row x elements
        

        
        
            

        
        
        self.maincontainer = maincontainer
        return self.maincontainer
    
    def graph_function(self):#this where you switch the dropdown and update the graph based on it
        global graphdata #28x30
        
        #create a and b dropdown
        lis=[]
        for i in range(16):
            lis.append("a"+str(i))
        for i in range(16):
            lis.append("b"+str(i))        
        
        temp1 = self.dropDown.get_value()
        temp2 = 0
        index = 0
        for i in lis:
            if (temp1 == i): #match dropdown selection with the pin number
                temp2 = index
            index=index+1
            
        self.mpl.ax.clear()
        self.mpl.ax.plot(graphdata[temp2])
        self.mpl.redraw()
        print(graphdata)
        print("graph data shape")
        print(graphdata.shape)

    
    
    def confirm_smart_schedule(self,widget):
        
        self.dialog = GenericDialog(title='Confirmation of Smart schedule', message='Are you sure you want to start Smart Scheduling? NOTE: Duration must be integer input. Wrong format will be interpreted as 0',width = '40%')
        self.dialog.show(self)
        self.dialog.confirm_dialog.do(self.smart_schedule)
        self.dialog.confirm_dialog.do(self.weatherPrediction)
    def confirm_smart_schedule_pack(self, widget):
        
        pass
    def ErrorMessage(self):
    
        self.dialog = GenericDialog(title='Error', message='There was an error with your schedule input',width = '40%')
        self.dialog.show(self)

    
    def smart_schedule(self,widget):
        global schedule_button_pressed
        global stoppressed
        global water_FIFO
        global total_children
        global smart_schedule_flag
        
        schedule_button_pressed = True
        stoppressed = False
        smart_schedule_flag = True
        water_FIFO = []
        
        schedule.clear() 
        schedule.every(7).days.do(self.weatherPrediction)
        schedule.every(1).minutes.do(self.xxx)
        schedule.every(15).seconds.do(self.save)#save and graph should be the same because save updates the graph values
        schedule.every(15).seconds.do(self.graph_function)
        
    


	
	# parameters require *sensor data: 1.) soil moisture 2.) temperature 3.) humidity
	#
	#                    ROW INFORMATION IS STORED IN TOTAL_CHILDREN[] (GLOBAL) which is retrieved through exec(0)
	#
    #                    *row information (all organized in object or array?)
	#                                  1.) time (time stored in total_children[])
	#                                  2.) day (days are stored in array based on boolean; array = [1,0,0,0,1,...])
	#                                  3.) duration (duration stored in total_children[])
	#                               (?)4.) pot size
	#           

	    
    def weatherPrediction(self,widget):
        global smart_duration
        global row_top_amount_index
        global smart_schedule_flag
        smart_schedule_flag = True
        
        sens_temp= 75
        #allocate a array of zeroes that matches shape of current existing rows.
        smart_duration= np.zeros(shape=(row_top_amount_index+1,7))
        #pull data from weather api: 1.) 7 day forecast
        #                               - weather type (sun, rain, etc), temperature
        #define thresholds for all values: 1.) soil moisture, temperature, humidity
        #all thresholds will be different depending on pot size 
        #adjust watering schedule based on weather data + sensor comparison
        global total_children
        #TODO: Determine thresholds based off testing
        
        # soil moistures interpreted as percentage range from 0 - 100
        soil_moisture_high = 100
        soil_moisture_low = 0
        
        # temperatures interpreted in F with general range of 40 - 115
        temperature_high = 4
        temperature_low = 0
        
        # humidity interpreted as value with general range of 0 - 100
        humidity_high = 100
        humidity_low = 0
        
        #precipitation thresholds include >30% for activation 
        precipitation_threshold = 100 
        
        #pulls weather values (up to 500 calls a day)
        weather_package = weatherAPI_pull()
        
        #i = row_number # TODO: store row info from website for determining decision
        
        #TODO: Figure out decision hierarchy 
        #DECISION HIERARCHY:
        for ij in range(row_top_amount_index+1):
	    # 1. Determine chosen days and durations
	        # Parse rows object
	        # =====================
            global days_pressed 
                #exec(f'global enabled\nenabled = {total_children[i][1]}.get_value()') # Unnecessary I think 
            exec(f'global days_pressed\ndays_pressed.append({total_children[ij][3]}.get_value())\ndays_pressed.append({total_children[ij][5]}.get_value())\ndays_pressed.append({total_children[ij][7]}.get_value())\ndays_pressed.append({total_children[ij][9]}.get_value())\ndays_pressed.append({total_children[ij][11]}.get_value())\ndays_pressed.append({total_children[ij][13]}.get_value())\ndays_pressed.append({total_children[ij][15]}.get_value())')
                # This will finalize days_pressed to have [1,0,1,0,1,0,0] for example, with index 0 starting from Monday (DAYS DONE)
                    
            global duration
                # Stores duration in form of string
                
            exec(f'global duration\nduration = {total_children[ij][-1]}.get_value()')

            print(days_pressed)#code is correct 
            # 2. Determine weather/temperature first.
                    
            # 3. From chosen days, view weather_packet
                # chosen days will be stored in boolean format ([0,1,0,0...]) 
                # for-loop through chosen days to return weather info (precip and temp (te mp will be converted and saved in fahrenheit))
            weather_dict = {}
            for i in range(0,7):
                weather_dict[str(weather_package[i]['datetime'].weekday())] = {'temperature': weather_package[i]['temp'], 'precipitation': weather_package[i]['precip']}
                
            today = int(list(weather_dict.keys())[i])
            print("today's index is " + str(today))
        
            combined_data = {}
        
            for j in range(0,7):
                
                if(days_pressed[j] == 1):
                   
                    smart_duration[ij][j] = duration
                    if(today > j):
                        algorithm = str((today+(7-(today-j)))%7)
                        combined_data[str(j)] = weather_dict[algorithm]
                        
                        
                    else:
                        algorithm = str((today+(j - today)%7))
                        combined_data[str(j)] = weather_dict[algorithm]
                    
                else:
                    combined_data[str(j)]=0
            # 4. From weather packet, if temperature OR precip pass thresholds, then perform adjustment
                # 4a. ADJUSTMENT (happens per day)
                    # Cases:
                        # 1. High Precip Rate / Rain
                            # Cancel watering for individual days with rain
                        # 2. High temperature / Harsh Sun
                            # Confirm Local Temperature first! -> use sens_temp and find difference (temp_diff) with weather_packet temp 
                            # if difference of |temp_diff| is > 5, then cancel (adjust based on DIFFERENCE?)
                            # if difference of |temp_diff| is < 5, then proceed with ADJUSTMENT
                            # Increase watering threshold by scaling
                                # For every 1 degree above threshold, increase soil moisture by X amount; or something like that
                            # Gauge X% increase of water through soil moisture sensors
                            # OLD IDEA:
                            #   Record amount of time taken to reach additional X% and store the "new duration"
                            # NEW IDEA: 
                            #   Record amount of time taken to reach additional X%
                            # Replace previous duration with "new duration"
                        # 3. Low temperature / Cloudy forecast
                            # Confirm local Temperature first!
                            # ... basically the same with high temperature's procedure by decrease soil moisture by X amount
                # 4b. NO ADJUSTMENT
                    # Just pass without doing anything
            
            combined_datas_keys = list(combined_data.keys())
            print(combined_data)
            for i in range(0, len(combined_data)):
               
                if (combined_data[str(j)] != 0):#doesnt run
                    curr_key = combined_datas_keys[i]
                    print(combined_data[curr_key])
                    api_temp = combined_data[curr_key]['temperature']
                    
    
                   # temperature_diff = abs(sens_temp-api_temp)
                    temperature_diff = 0
                    print("first if ")
                    if(combined_data[curr_key]['precipitation'] > precipitation_threshold):
    
                        
                        #exec(f'{total_children[0][-1]}.set_value({0})')
                        #TODO: Adjust duration value; turning it to 0 (CANCEL Watering)
                        smart_duration[ij][j] = 0
                        print("2nd if ")
    
                    else:
                        if(temperature_diff < 5):
    
                            if(combined_data[curr_key]['temperature'] > temperature_high):
                                #TODO: Adjust duration value directly; lowering it by a scaled amount per degree
                                smart_duration[ij][j] = smart_duration[ij][j] + 5
                                print("add5 ")
                            elif(combined_data[curr_key]['temperature'] < temperature_low):
                                #TODO: Adjust duration value directly; raising it by a scaled amount per degree
                                if (smart_duration[ij][j]-5>0 ): #if you can reduce it by 5 seconds then do it
                                    smart_duration[ij][j] = smart_duration[ij][j] - 5
                                    print("sub5 ")
                                elif (smart_duration[ij][j]-5<0 ):#else just turn it to 0
                                    smart_duration[ij][j] = 0
                                    print("set to 0")
                    
                else:
                    smart_duration[ij][j] = -1
        days_pressed=[] #clear days_pressed to reset
        print (smart_duration)


    

    
    def save(self):
        global sensor
        global sensor_table
        sensor_number = 1
        sensor_list = []
        sensor_table = []
        self.dialog = GenericDialog(title='Sensor Values',  width='500px')
        ser1 = myfile = open('/dev/ttyACM0',"r", encoding = "ISO-8859-1")
        ser1.flush()
        serialdata = ser1.readlines()
        serialdata = serialdata[-1]

        ser2 = myfile2 = open('/dev/ttyACM1',"r") #
        ser2.flush()
        serialdata2 = ser2.readlines()
        serialdata2 = serialdata2[-1]
        
        serialdata = serialdata + serialdata2
        sensorvalues = serialdata.split(",")#array of (pin number+21) + (actual sensorvalue)
        try:
            sensorvalues.remove("\n")
        except:
            pass
        global graphdata #32x30
        index = 0
        print("length of sensorvalues")
        print(len(sensorvalues))
        print("actual sensor values")
        print (sensorvalues)
        for f in range(1,len(sensorvalues),2): #for each pair of sensor values 
            try:
                temp = np.zeros((30,), dtype = int) #create temporary array, data points buffer is 30 
                temp = graphdata[index][1:len(graphdata[index])] #copy over everything but the first
                temp = np.append(temp,sensorvalues[f])#add the sensor value to the end
                graphdata[index]=temp #set that graph data row to the new array of sensor values
                index=index+1;
            except:
                print("Couldn't read. Trying again")
        print (graphdata)
     
        
        
        
        
        
        sensorvalues = serialdata.split(",")#array of (pin number+21) + (actual sensorvalue)
        try:
            sensorvalues.remove("\n")
        except:
            pass
        for f in range(1,len(sensorvalues),2): #this loop marks pin numbers and values that are <20 with x so they will be deleted.
            if (int(f)==0):
                sensorvalues[f]='x' #if the analog reading is 0, mark for deletion# list assignment out of range
                sensorvalues[f-1]='x'  #also mark pin number for deletion
        
        sensorvalues = [x for x in sensorvalues if x!='x'] #delete all that are marked for deletion
        
        sensor_table.append(("Pin Number",'Sensor Reading'))
        for amount_of_sensor_values in range(0,len(sensorvalues),2):
            sensor_list.append(sensorvalues[amount_of_sensor_values]) #append the pin number 
            try:
                sensor_list.append(sensorvalues[amount_of_sensor_values+1])#then append 
            except:
                print("Failed to append (save function)")
            sensor_table.append(tuple(sensor_list))
            sensor_list = []
        
        global file_index #we need these to persist throughout future operations 
        global today
        global row
        global row_top_amount_index
        global total_children
        global mailbox
        #datetime.datetime.today().weekday()
        if (datetime.datetime.today().weekday()!=today):#switch to next day and next file if day change is detected, if it's still the same day, don't switch files
            file_index=(file_index+1)%30 #29 is max, 30 is 0
            today = datetime.datetime.today().weekday()#also make this line run once at the beginning as well.
            mode = 'w' #overwrite if wrapped around
        else:
            mode = 'a'#if still same day, then append
        with open(files[file_index],mode) as file_write:
            local_list = []
            writer_object = writer(file_write)
            local_list.append("DATE: ")
            local_list.append(datetime.date.today())#append the date
            now = datetime.datetime.now()
            current_time = now.strftime("%H:%M:%S")
            local_list.append("TIME: ")
            local_list.append(current_time)#append the time
            writer_object.writerow(local_list) #put those 2 in file
            writer_object.writerow("") 
            local_list=[] #clear for the next
            for i in range(row_top_amount_index+1):
                file_write.write(f'Row No. {i+1}')
                writer_object.writerow("")
                
                writer_object.writerow(['Enabled?','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday','Start','End','Interval','Duration'])
                for l in range(1,17,2):#gather all the checkboxes, append to list, write the list, then clear	
                    exec(f'global mailbox\nmailbox = {total_children[i][l]}.get_value()')
                    local_list.append(mailbox)
                exec(f'global mailbox\nmailbox = {total_children[i][18]}.get_value()')
                local_list.append(mailbox)
                exec(f'global mailbox\nmailbox = {total_children[i][20]}.get_value()')
                local_list.append(mailbox)
                exec(f'global mailbox\nmailbox = {total_children[i][22]}.get_value()')
                local_list.append(mailbox)
                exec(f'global mailbox\nmailbox = {total_children[i][24]}.get_value()')
                local_list.append(mailbox)
                writer_object.writerow(local_list)
                local_list=[] 
                file_write.write(f'--------------------------------------------------------')
                writer_object.writerow("")
            for l in sensor_table:#write the sensor values
                writer_object.writerow(l)
            sensor_table=[]
            file_write.write(f'===============================================================')
            writer_object.writerow("")
            file_write.close()    
    
    
    
    
    

        #regular schedule

    def xxx(self):
        global water_FIFO
        global thread_3_alive
        global stoppressed
        global days_pressed
        global schedule_button_pressed
        global row_top_amount_index
        global total_children
        global matchingtimes
        
        global smart_schedule_flag
        global smart_duration
        matchingdays=False
        matchingtimes=False
  
        i=0
        for i in range(row_top_amount_index+1): #for each existing row
            global days_pressed
            #check if the row enable is pressed
            days_pressed = []
            exec(f'global enabled\nenabled = {total_children[i][1]}.get_value()')#it says here that self is not defined
            
            exec(f'global days_pressed\ndays_pressed.append({total_children[i][3]}.get_value())\ndays_pressed.append({total_children[i][5]}.get_value())\ndays_pressed.append({total_children[i][7]}.get_value())\ndays_pressed.append({total_children[i][9]}.get_value())\ndays_pressed.append({total_children[i][11]}.get_value())\ndays_pressed.append({total_children[i][13]}.get_value())\ndays_pressed.append({total_children[i][15]}.get_value())')
            #[1,0,1,0,1,0,0]
            global enabled
            global schedule_button_pressed
            print(f"for row{i} enabled = {enabled}, stoppressed = {stoppressed}, schedulebutton = {schedule_button_pressed}")
            if (enabled and stoppressed==False and schedule_button_pressed ==True): #if the enable was pressed, and stop button is not pressed, and schedule button was pressed
                #global days_pressed #in my exp, any variable in exec must be globalized again
                print("In the loop that checked if enable was pressed")
                print (f"days = {days_pressed}")
                #check if days match
                #get today's weekday
                temp = datetime.datetime.today().weekday()
                for ii in range(7):
                    if (temp==ii and days_pressed[ii]==True):#the logic is this: for each day, if today is the weekday and the weekday's checkbox is pressed, there is a match
                        matchingdays=True
                        
                        
                        if (matchingdays):#if days are matching now check if times are matching
                            
                            
                            exec(f'global matchingtimes\nglobal interval\nmatchingtimes=(timesplitter({total_children[i][18]}.get_value(),{total_children[i][20]}.get_value(),{total_children[i][22]}.get_value()))')
                            
                            
                            if (matchingtimes!='error' and matchingtimes == True):#if it returns error 
                                exec(f'global durationed\ndurationed = {total_children[i][-1]}.get_value()')
                                global durationed
                              
                                
                                durationed = checknonsensevalues(durationed)
                                
                                if (smart_schedule_flag == False):
                                    if (durationed!=0):
                                        water_FIFO.append(SprinklerGPIOs[i])
                                        water_FIFO.append(durationed)
                                else: #if smart_schedule_flag == true, use the smart duration array with the current's day's index
                                    water_FIFO.append(SprinklerGPIOs[i])
                                    water_FIFO.append(smart_duration[i][datetime.today().weekday()])
                                matchingdays=False
                                matchingtimes=False
                            if (matchingtimes=='error'):
                                schedule.clear()
                                self.ErrorMessage()
        
        
        
    def confirm_create_row(self,widget):
        self.dialog = GenericDialog(title='Confirmation of Create row', message='Are you sure you want to create row? Schedules will be reset',width = '40%')
        self.dialog.show(self)
        self.dialog.confirm_dialog.do(self.createrow)
        
    def open_fileselection_dialog(self, widget):
        self.fileselectionDialog = gui.FileSelectionDialog('File Selection Dialog', 'Select files', False,
                                                           '.')
        self.fileselectionDialog.confirm_value.do(
            self.on_fileselection_dialog_confirm)

        # here is returned the Input Dialog widget, and it will be shown
        self.fileselectionDialog.show(self)
        
    def on_fileselection_dialog_confirm(self, widget, filelist):
        # a list() of filenames and folders is returned
        print(filelist)
        if len(filelist):
            self.filename = filelist[0]
            self.execute_javascript('window.location = "/%s/direct_download"'%str(id(self)))

    def direct_download(self):
        with open(self.filename, 'r+b') as f:
            content = f.read()
            headers = {'Content-type': 'application/octet-stream',
                'Content-Disposition': 'attachment; filename="%s"' % os.path.basename(self.filename)}
            return [content, headers]

		
    def createrow(self,widget):
        schedule.clear()
        global button_top
        global total_children
        global addrowbuttonpressed
        global row_top_amount_index
        global smart_schedule_flag
        global schedule_button_pressed
        smart_schedule_flag = False
        schedule_button_pressed = False
        addrowbuttonpressed=True #send thread1 a message that a row needs to be created
        time.sleep(3)#give the thread time to create the new rows, otherwise it will require a refresh 
        if (row_top_amount_index<25):
            button_top+=1.3
            self.btcontainer.css_top = f"{button_top}%"
        del total_children
        total_children = []#reset the total_children (cause there's more after we created the row)
        for i in vars(self.maincontainer)['children']:
            total_children.append(i)#this contains all elements of the page
        # total_children.remove('deleterow') #delete the delete row button
        # total_children.remove('addrow') #delete the addrow button
        # total_children.remove('RunOnceButton')
        # total_children.remove('StopButton')
        # total_children.remove("ScheduleButton")
        # total_children.remove("SensorButton")
        # total_children.remove("SmartScheduleButton")
        # total_children.remove('download')
        # total_children.remove('graphbt')
        total_children.remove("self.dropDown")
        total_children.remove("self.mpl")
        # total_children.remove("Reboot")
        total_children.remove("self.btcontainer")
        

        total_children=np.array(total_children)


        total_children = np.reshape(total_children,(1+row_top_amount_index,25)) #everything was in one long list, now i'm making it 2d row x elements
        


    def delete_row(self,widget):
        global total_children
        global button_top
        global addrowbuttonpressed
        global row_top_amount_index #TODO: remember to decrement these even the gray color so that the add row doesn't skip numbers
        global bool_gray
        if (row_top_amount_index>=1):
            bool_gray=not bool_gray #swappign the color so that they will swap back when you add row
            for i in total_children[row_top_amount_index]:
                exec(f'self.maincontainer.remove_child({i})')
     #move back the number by 1 so that when you add row it doesn't skip numbers
            row_top_amount_index-=1
            total_children=np.delete(total_children,-1,0)
            print(total_children)
            button_top-=1.3
            self.btcontainer.css_top = f"{button_top}%"
           
        else:
            print(row_top_amount_index)
    def stop(self,widget):
        global water_FIFO
        global thread_2_alive
        global stoppressed
        global smart_schedule_flag
        smart_schedule_flag = False #pressing stop stops the smart schedule
        schedule_button_pressed = False #also stops the scheduling
        schedule.clear()
        stoppressed=True #there's a flag in the watering that stops the function when this is true
        water_FIFO=[]#clear the watering thread's tasks
    
    def confirm_run_once(self,widget):
        
        self.dialog = GenericDialog(title='Confirmation of Run Once', message='Are you sure you want to Run Once with these values? NOTE: Duration must be integer input. Wrong format will be interpreted as 0',width = '40%')
        self.dialog.show(self)
        self.dialog.confirm_dialog.do(self.run_once)
        
    def confirm_schedule(self,widget):
        self.dialog = GenericDialog(title='Confirmation of Schedule', message='Are you sure you want to Schedule these values?\nNOTE: Time must be in 4 integer digits (24 hr format. Eg: 1359). Duration must be integer input\nWrong format will cause no operation')
        self.dialog.show(self)
        
        #self.dialog.confirm_dialog.do(self.xxx)  
        #self.dialog.confirm_dialog.do(self.start_schedule)
        self.dialog.confirm_dialog.do(self.confirm_schedule_pack)
        
  
    def confirm_schedule_pack(self,widget):
        global stoppressed
        global schedule_button_pressed
        global smart_schedule_flag
        stoppressed = False
        schedule_button_pressed = True
        smart_schedule_flag = False
        #what this does is that it runs once immediately and every other minute
        self.xxx()
        
        self.start_schedule(widget)
        
        
    def start_schedule(self,widget):
        print ("REGULAR SCHEDULE STARTED")
        global schedule_button_pressed
        global stoppressed
        global water_FIFO
        global total_children
        global smart_schedule_flag
        smart_schedule_flag = False #starting regular scheudle cancels smart
        water_FIFO= []
        schedule_button_pressed = True
        stoppressed = False
        schedule.clear() #clear current schedule
        schedule.every(1).minutes.do(self.xxx)
        schedule.every(15).seconds.do(self.save)
        schedule.every(15).seconds.do(self.graph_function)        
        print('aye captain, schedule set')
            
    def Reboot(self,widget):
        os.system("sudo reboot")

    def run_once(self,widget):
        global smart_schedule_flag 
        global row_top_amount_index
        global total_children
        global water_FIFO
        global SprinklerGPIOs
        global thread_2_alive
        global stoppressed
        global schedule_button_pressed

        
        smart_schedule_flag = False #running a manual watering session cancels smart schedule
        
        
        
        water_FIFO=[] #if you spam the runonce button rather than adding to the queue, you just reset it and start over
        schedule_button_pressed = False
        
        stoppressed=False #clear that flag that pauses the thread
        
        #this button will only take in the duration and row enable. NO schedule considerations.
        
        #for each row
        #first check if today matches the checked day
        #then check if the time matches the right time
        #if both checks complete, append gpio and duration to the FIFO water processing queue, where a thread will do the watering.
        for i in range(row_top_amount_index+1):#only check the existing rows
            exec(f'global enabled\nenabled = {total_children[i][1]}.get_value()')#2nd element is the row enable
            exec(f'global durationed\ndurationed = {total_children[i][-1]}.get_value()')
            if (enabled):#if the enable checkbox is checked then check the duration
                
                global durationed#why the fuck does durationed need to be globalized again
                # last element is the duration, it's currently a string so you need to turn it into an int
                #if the duration is blank or '' replace with 0
                durationed=checknonsensevalues(durationed)
                if (durationed):
                    water_FIFO.append(SprinklerGPIOs[i])
                    water_FIFO.append(durationed)
                print(f'before: {water_FIFO}')
       
            
    def GrabSensorValues(self,widget):
        time.sleep(5)
        global sensor
        global sensor_table
        sensor_number = 1
        sensor_list = []
        sensor_table = []
        self.dialog = GenericDialog(title='Sensor Values',  width='500px')
        ser1 = myfile = open('/dev/ttyACM0',"r") #
        ser1.flush()
        serialdata = ser1.readlines()
        serialdata = serialdata[-1]
        
        ser2 = myfile2 = open('/dev/ttyACM1',"r") #
        ser2.flush()
        serialdata2 = ser2.readlines()
        serialdata2 = serialdata2[-1]
        
        serialdata = serialdata + serialdata2
        
        
        
        
        print("Serial Data Raw From Arduinos:")
        print(serialdata)
        sensorvalues = serialdata.split(",") #array of (pin number+21) + (actual sensorvalue)
        print("Sensor Values without Filtering:") #this part is already removing values, which is not intended 
        print(sensorvalues)
        try:
            sensorvalues.remove("\n")
            sensorvalues.remove(" \n")
        except:
            pass
        for f in range(1,len(sensorvalues),2): #this loop marks pin numbers and values that are <20 with x so they will be deleted.
            if (int(sensorvalues[f])==0):
                sensorvalues[f]='x' #if the analog reading is 0, mark for deletion# list assignment out of range
                sensorvalues[f-1]='x'  #also mark pin number for deletion
        sensorvalues = [x for x in sensorvalues if x!='x'] #delete all that are marked for deletion
        print ("Sensor values Filtered:")
        print(sensorvalues)
        sensor_table.append(("Pin Number",'Sensor Reading'))
        try:
            sensorvalues.remove("\n")
            sensorvalues.remove(" \n")
        except:
            pass
        for amount_of_sensor_values in range(0,len(sensorvalues),2):
            sensor_list.append(sensorvalues[amount_of_sensor_values]) #append the pin number which has been increased by 21 for filtering purposes
            try:
                sensor_list.append(sensorvalues[amount_of_sensor_values+1])#why does this say list index out of range
            except:
                print("failed to append line 1199")
            sensor_table.append(tuple(sensor_list))
            sensor_list = []
             

        self.table = Table.new_from_list(sensor_table, width=500, height=200, margin='10px')
        self.dialog.add_field('table',self.table)
    


        self.dialog.show(self)




    def on_close(self):
        global thread_1_alive
        global thread_2_alive
        global thread_3_alive
        thread_1_alive=False
        thread_2_alive=False
        thread_3_alive=False
        schedule.clear()
        print("########################################## TERMINATED pEniS####################################") #this makes sure the threads die when the site is ctrl-c'd
        #or else you get zombies 
        super(WaterControl, self).on_close()


message = get_ip()
send_sms_via_email(number, message, provider, sender_credentials)
if __name__ == "__main__":
    # starts the webserver
    # optional parameters
   #change the address to the address of whatever is hosting this. 
   #change address to wlan0 using ifconfig on the terminal

    start(WaterControl, debug=True, address=get_ip(), port=8000,start_browser=False, multiple_instance=False)
    #ifconfig and get the inet sht


