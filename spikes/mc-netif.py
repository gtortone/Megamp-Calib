
import netifaces as ni

#print(ni.ifaddresses('eth0'))

try:
   ip = ni.ifaddresses('eth0')[ni.AF_INET][0]['addr']
except Exception as e:
   print(e)
else:
   print(ip)  
