# import SDK packages
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from time import sleep
import time
from gpiozero import MCP3008, LED, Buzzer
import picamera
import base64
import json

# Instatiate sensors
adc = MCP3008(channel=0)
led = LED(18)
bz = Buzzer(5)
camera = picamera.PiCamera()

# Hardcoded Location
location = "Singapore Polytechnic T2034"

# Declarations
soundThreshold = 400

######## Start of AWS ########

# Custom MQTT message callback for device/pi/connected
def devicePiConnectedCallback(client, userdata, message):
	print("Received a new message: ")
	print(message.payload)
	print("from topic: ")
	print(message.topic)
	print("--------------\n\n")


# Custom MQTT message callback for Sound Threshold MQTT
def soundThresholdCallback(client, userdata, message):
	# Global var
	global soundThreshold

	msg = str(message.payload.decode("utf-8"))

	# Process subcribed json message
	deserialized = json.loads(msg)
	soundThreshold = str(deserialized['soundThreshold'])


# AWS Credentials
host = "a2lqw7hkum5oos.iot.ap-southeast-1.amazonaws.com"
rootCAPath = "rootca.pem"
certificatePath = "certificate.pem.crt"
privateKeyPath = "private.pem.key"

# AWS Configurations
my_rpi = AWSIoTMQTTClient("basicPubSub")
my_rpi.configureEndpoint(host, 8883)
my_rpi.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

my_rpi.configureOfflinePublishQueueing(-1) # Infinite offline Publish queueing 
my_rpi.configureDrainingFrequency(2) # Draining: 2 Hz
my_rpi.configureConnectDisconnectTimeout(10) # 10 sec
my_rpi.configureMQTTOperationTimeout(5) # 5 sec


# Connect to AWS IoT
my_rpi.connect()
print("RPI is connected to AWS IoT!")


# After connecting, subscribe to topics
my_rpi.subscribe("preferences/soundThreshold", 1, soundThresholdCallback)
print("RPI is subscribed to preferences/soundThreshold")

my_rpi.subscribe("devices/pi/connected", 1, devicePiConnectedCallback)
print("RPI is subscribed to devices/pi/connected")

sleep(3)

######## End of AWS ########


# Constantly get inputs from FC-109 Microphone Amplifier via MCP3008 ADC
def startMain():

	print("Sound from WEBA: " + str(soundThreshold))

	# Read FC-109 input and format to 2 decimal places
	soundInput = format(float(adc.value * 1024), '.2f')

	# Round value to closest integer
  val = int(round(float(soundInput)))
	newSoundThreshold = int(round(float(soundThreshold)))
	print("Sound from surroundings: " + str(val))
	sleep(1)

	# If sound is above a certain threshold, take photo & send data to MQTT
	if val > newSoundThreshold:
		print("Value from surroundings is higher than volume from WEBA!")
	
		# Get current dateTime timestamp
		timestring = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
	
		# photoUrl
		photoUrl = '/home/pi/Desktop/iotca2/Photos/photo_'+timestring+'.jpg'
	
		# Capture image
		print("Photo is captured!")
		camera.capture(photoUrl, resize=(500,281))
		camera.stop_preview()
	
		# Switch on Buzzer & LED
		print("LED & Buzzer is switched on!")
		led.blink()
		bz.on()
	
		# Publish all data to MQTT (sensor/alert) (sound, location, image) 
	  publishToSensorAlertMqtt(photoUrl, location, val)


		# After 10 seconds,
		# Switch off Buzzer & LED
		sleep(10)

		led.off()
		bz.off()

# Encode captured image to base64
def convertImageToBase64(photoUrl):
	# Encode image to base64
	with open(photoUrl, "rb") as image_file:
		encodedImage = base64.b64encode(image_file.read())
		return encodedImage


# Publish data to sensor/alert MQTT
def publishToSensorAlertMqtt(photoUrl, location, val):
	encodedImage = convertImageToBase64(photoUrl)
	msg = '{"location": "'+location+'", "sound": '+ str(val) +', "image": "'+str(encodedImage)+'"}'
	my_rpi.publish("sensors/alert", msg, 1)
	print("SENT ALERT TO SERVER VIA MQTT")
	sleep(3)

# Publish data to devices/pi/connected MQTT
connectedMsg = '{ "new": true }'
my_rpi.publish("devices/pi/connected", connectedMsg, 1)


# Run program in infinite loop
while True:
  startMain()