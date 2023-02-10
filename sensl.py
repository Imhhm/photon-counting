import ctypes
import os
import numpy as np

class HRMTimeAPI():
	def __init__(self):
		# Load DLL into memory
		SENSL = r'C:\Program Files (x86)\sensL\HRM-TDC\HRM_TDC DRIVERS'
		os.environ['PATH'] = ';'.join([SENSL, os.environ['PATH']])
		self.dll = ctypes.WinDLL(os.path.join(SENSL, 'HRMTimeAPI.dll'))
		
		# Set up connection to device
		self.dll.HRM_RefreshConnectedModuleList()
		ModuleCount = self.dll.HRM_GetConnectedModuleCount()
		if ModuleCount == 1:
			handle_array_type = ctypes.c_void_p*1 # Array of 1 void
			HandleArray = handle_array_type()
			self.dll.HRM_GetConnectedModuleList.restype = handle_array_type
			HandleArray = self.dll.HRM_GetConnectedModuleList(HandleArray)
			self.ModuleHandle = HandleArray[0]
		else:
			print 'Number of modules present =', ModuleCount
        print "Using Time = FrameNo*4000000. + MICRO*26.9851# This gives non-integer values."
        #print "Time = FrameNo*4000001.373 + MICRO*26.9851 # Gives integer number of 26.9851ps"
	def TimeTags2Mem(self,ncounts=10000000,recordinglength=1000,esr=0xAAAA,microlsb=0,algorithm='ReSync'):
		# change esr to account for 3 and 4 channels
		if ncounts<=10000000:
			# Set resync mode
			self.dll.HRM_SetFrequencySelectionRegister(self.ModuleHandle,0xFFFF)
			
			bufsize = 8*ncounts # memory size of buffer in bytes
			
			buftype = ctypes.c_uint32*(2*ncounts)
			buf = buftype()
			#buf = ctypes.create_string_buffer(bufsize)
			
			buf_p = ctypes.pointer(buf) # pointer to memory buffer
			recordedbytes = ctypes.c_int() # location for storing actual number of bytes recorded
			recordedbytes_p = ctypes.pointer(recordedbytes) # pointer to location for storing actual number of bytes recorded
			self.dll.HRM_StreamTimeTags2Mem(self.ModuleHandle,buf_p,bufsize,recordinglength,esr,microlsb,recordedbytes_p)
			ntags = recordedbytes.value / 8
			
			a = np.frombuffer(buf,dtype=int,count=ntags*2)
			CHANNEL = np.bitwise_and(a[::2],3)
			MICRO = a[::2]>>2
			MACRO = a[1::2]
			
			if algorithm == 'ReSync':
				MACROoffset = (MACRO[0] - MICRO[0]*26.9851/25000).astype(int)
				FrameNo = (MACRO-MACROoffset)/160
				Remainder = np.remainder(MACRO-MACROoffset,160)
				FrameNo[(Remainder<60) & (MICRO > 100000)] += -1
				FrameNo[(Remainder>110) & (MICRO < 40000)] += 1
				Time = FrameNo*4000000. + MICRO*26.9851 # technically correct but use below for integer number of 26.9851ps
				#Time = FrameNo*4000001.373 + MICRO*26.9851 # Gives integer number of 26.9851ps
				
				# Sort time tags into time order and output to array
				sorter = np.argsort(Time)
				data = np.zeros((len(CHANNEL),2))
				data[:,0] = CHANNEL[sorter]
				data[:,1] = Time[sorter]
			
			if algorithm == 'FreeRuning':
				# NOT CURRENTLY WORKING
				# works provided the time between consecutive time tags is not greater than 21.5 seconds
				dMACRO = MACRO[1:]-MACRO[:-1]
				sel = MACRO[:-1]>MACRO[1:]
				dMACRO[sel] += 0x100000000
				rMICRO = 143248136.6016 # rollover time in ps
				nMICRO = (dMACRO*5000)/rMICRO # *5000 to convert dMACRO into ps
				dMICRO = MICRO[1:]-MICRO[:-1]
				sel = MICRO[:-1]>MICRO[1:]
				dMICRO[sel] += 0x510000
				dTIME = nMICRO*rMICRO + dMICRO*26.9851
				data = np.zeros((len(CHANNEL),2))
				data[:,0] = CHANNEL
				data[:,1] = dTIME
		
		return data
	
	def TimeTags2CSV(self,Filename,StreamTime=1000,ESR=0x0055):
		# Set resync mode
		self.dll.HRM_SetFrequencySelectionRegister(self.ModuleHandle,0xFFFF)
		# Set maximum number of time tags to record (if set to zero time tagging continues for StreamTime)
		#self.dll.HRM_SetMemoryCountRegister(self.ModuleHandle, 1000) # currently does nothing
		# Collect FIFO time tag data in resync mode
		self.dll.HRM_StreamTimeTags2File(self.ModuleHandle,Filename+'.raw',StreamTime,ESR,0) # integration time in ms
		# Try-Except to ignore the wrong calling convention error
		try:
			self.dll.HRM_ConvertRAWtoCSV(2,0,Filename+'.raw',Filename+'.csv')
		except:
			None

if __name__ == "__main__":
	HRMTime = HRMTimeAPI()
	HRMTime.TimeTags2Mem()
