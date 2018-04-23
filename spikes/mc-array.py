
import array
import struct

v = array.array('B')

v.append(1)
v.append(2)
v.append(3)
v.append(4)

for i in v:
   print(i)

print('###')

count = len(v) // 2
vint = struct.unpack('H'*count, v)

for i in vint:
   print(i)

print(vint)
