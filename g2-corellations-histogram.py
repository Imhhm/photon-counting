# v7, fixed first bin on histogram
# v8, wx.SAVE|wx.OVERWRITE_PROMPT changed to wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT 
from __future__ import division
from sensl import HRMTimeAPI
import wx
import matplotlib
matplotlib.use('WxAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg, NavigationToolbar2WxAgg
import matplotlib.pyplot as plt
import numpy as np
import threading
import time
import sys
import os



def bindata(x,y,binfac=0):
    for i in range(binfac):
        y = (y[:-1:2]+y[1::2])
        x = (x[:-1:2]+x[1::2])/2
    return x,y

class MainFrame(wx.Frame):
    def __init__(self,parent,title):
        ''' init method for main frame '''
        #self.temp_output = [] # To hold count rates at each timestep
        #self.t0 = 0 # time when run is started
        #self.t1 = 0 # time when save happens
        
        print 'self.width = 1.5e3 '
        
        wx.Frame.__init__(self,parent,title=title)
        
        self.HRMTime = HRMTimeAPI()
        
        ########### Init Params ###########
        self.recordinglength = 1000 # ms
        self.ncounts = 1000000
        self.dtmax = 100000 # ps # max correlation time between herald and signal
        self.dntags = 3 # number of time tags to consider for calculating the cross correlation
        self.plotbinfactor = 3 # number of time bins to combine for plot
        self.DataCollectFlag = False # Dont collect data at program start
        self.dirname = ''
        self.cumulativeflag = True #rsm
        self.autosaveflag = False #rsm
        self.autosaverate = 10.0 #rsm
        
        if self.autosaveflag == True:
            print "Autosaving when Ch0 rate drops below (kHz): ",self.autosaverate
        else:
            print "NOT autosaving"
        ########### Right Panel ############
        self.rightpanel = wx.Panel(self,style=wx.BORDER)
        
        self.combobox = wx.ComboBox(self.rightpanel,choices=['Cross Correlation','Heralded Cross Correlation','Auto Correlation C0','Auto Correlation C1','Auto Correlation C2'],style=wx.CB_DROPDOWN)
        self.combobox.SetValue('Cross Correlation')
        self.Bind(wx.EVT_COMBOBOX, self.OnComboSelect, self.combobox)
        
        self.cumulativetickboxtextlabel = wx.StaticText(self.rightpanel,label='Cumulative mode?')
        self.cumulativetickbox = wx.CheckBox(self.rightpanel)
        self.cumulativetickbox.SetValue(True) #rsm
        self.tickboxsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.tickboxsizer.Add(self.cumulativetickboxtextlabel,1,wx.EXPAND)
        self.tickboxsizer.Add(self.cumulativetickbox,0,wx.EXPAND)
        
        #self.autosavetickboxtextlabel = wx.StaticText(self.rightpanel,label='Autosave mode?')
        #self.autosavetickbox = wx.CheckBox(self.rightpanel)
        #self.autosavetickbox.SetValue(True) #rsm
        #self.tickboxsizer = wx.BoxSizer(wx.HORIZONTAL)
        #self.tickboxsizer.Add(self.autosavetickboxtextlabel,1,wx.EXPAND)
        #self.tickboxsizer.Add(self.autosavetickbox,0,wx.EXPAND)
        
        
        self.rightpaneltextctrls = []
        self.rightpaneltextlabels = []
        self.rightpaneltextctrls.append(wx.TextCtrl(self.rightpanel,value=str(self.recordinglength)))
        self.rightpaneltextlabels.append(wx.StaticText(self.rightpanel,label='Max recording time (s)'))
        self.rightpaneltextctrls.append(wx.TextCtrl(self.rightpanel,value=str(self.ncounts)))
        self.rightpaneltextlabels.append(wx.StaticText(self.rightpanel,label='Max number of counts'))        
        self.rightpaneltextctrls.append(wx.TextCtrl(self.rightpanel,value=str(self.dtmax)))
        self.rightpaneltextlabels.append(wx.StaticText(self.rightpanel,label='Max correlation time (ps)'))        
        self.rightpaneltextctrls.append(wx.TextCtrl(self.rightpanel,value=str(self.plotbinfactor)))
        self.rightpaneltextlabels.append(wx.StaticText(self.rightpanel,label='Plot binning factor'))    
        self.rightpaneltextctrls.append(wx.TextCtrl(self.rightpanel,value=str(self.dntags)))
        self.rightpaneltextlabels.append(wx.StaticText(self.rightpanel,label='# of tags per trigger'))
        
        self.applybutton = wx.Button(self.rightpanel, wx.ID_ANY, 'Apply')
        self.Bind(wx.EVT_BUTTON, self.OnApply, self.applybutton)
        
        # Create sizer
        self.rightpanelsizer = wx.BoxSizer(wx.VERTICAL)
        self.rightpanelsizer.Add(wx.StaticText(self.rightpanel,label='Settings',style=wx.ALIGN_CENTRE_HORIZONTAL),0,wx.EXPAND|wx.ALL,border=10)
        self.rightpanelsizer.Add(self.combobox,0,wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,border=10)
        self.rightpanelsizer.Add(self.tickboxsizer,0,wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,border=10)
        for i in range(len(self.rightpaneltextctrls)):
            self.rightpanelsizer.Add(self.rightpaneltextlabels[i],0,wx.EXPAND|wx.LEFT|wx.RIGHT,border=10)
            self.rightpanelsizer.Add(self.rightpaneltextctrls[i],0,wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,border=10)
        self.rightpanelsizer.Add(self.applybutton,0,wx.EXPAND|wx.LEFT|wx.RIGHT,border=10)
        
        # Layout sizer
        self.rightpanel.SetSizerAndFit(self.rightpanelsizer)

        ########## Create Left Panel ##########
        self.leftpanel = wx.Panel(self)
        
        ########### Plot Panel ############
        self.plotpanel = wx.Panel(self.leftpanel)
        self.fig = plt.figure(figsize=(8,4.944),facecolor='white')

        self.canvas = FigureCanvasWxAgg(self.plotpanel, wx.ID_ANY, self.fig)
        self.navtoolbar = NavigationToolbar2WxAgg(self.canvas)

        # Create sizer
        self.plotsizer = wx.BoxSizer(wx.VERTICAL)
        self.plotsizer.Add(self.canvas, 1, wx.LEFT|wx.RIGHT|wx.GROW,border=0)
        self.plotsizer.Add(self.navtoolbar, 0, wx.LEFT|wx.RIGHT|wx.EXPAND,border=0)

        # Layout sizer
        self.plotpanel.SetSizerAndFit(self.plotsizer)
        
        ########### Top Button Panel ###########
        self.topbuttonpanel = wx.Panel(self.leftpanel)
        self.topbuttons = []
        self.topbuttons.append(wx.Button(self.topbuttonpanel, wx.ID_ANY, 'Run Once'))
        self.Bind(wx.EVT_BUTTON, self.OnRunOnce, self.topbuttons[-1])
        self.topbuttons.append(wx.Button(self.topbuttonpanel, wx.ID_ANY, 'Run Continuous'))
        self.Bind(wx.EVT_BUTTON, self.OnRunContinuous, self.topbuttons[-1])
        self.topbuttons.append(wx.Button(self.topbuttonpanel, wx.ID_ANY, 'Stop'))
        self.Bind(wx.EVT_BUTTON, self.OnStop, self.topbuttons[-1])
        self.topbuttons.append(wx.Button(self.topbuttonpanel, wx.ID_ANY, 'Save Correlation Data'))
        self.Bind(wx.EVT_BUTTON, self.OnSaveCorrelation, self.topbuttons[-1])
        
        # Create sizer
        self.topbuttonsizer = wx.BoxSizer(wx.HORIZONTAL)
        for i,button in enumerate(self.topbuttons):
            self.topbuttonsizer.Add(button, 1, wx.EXPAND)

        # Layout sizer
        self.topbuttonpanel.SetSizerAndFit(self.topbuttonsizer)
        
        ######### Left panel sizer ##########
        self.leftsizer = wx.BoxSizer(wx.VERTICAL)
        self.leftsizer.Add(self.topbuttonpanel,0,wx.EXPAND)
        self.leftsizer.Add(self.plotpanel,1,wx.EXPAND)
        self.SetSizerAndFit(self.leftsizer)
        
        ######### Top level sizer #############
        self.topsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.topsizer.Add(self.leftpanel, 1, wx.EXPAND)
        self.topsizer.Add(self.rightpanel, 0, wx.EXPAND)
        self.SetSizerAndFit(self.topsizer)
        
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel('Delay (ns)')
        self.ax.set_ylabel('Unnormalised Cross Correlation')
        self.ax.autoscale(tight=True)
        #self.ax.minorticks_on()
        self.ax.tick_params(axis='both', which='both', bottom=True)
        self.canvas.draw()

        self.Show()
        #print "Code adds a delay to Ch0thenCh1(20ns) and a delay to Ch0thenCh2 (10ns)"
        
    def CalcCorrelation(self):
        if self.combobox.GetValue() == 'Cross Correlation':
            self.CrossCorrelation()
        elif self.combobox.GetValue() == 'Heralded Cross Correlation':
            self.HeraldedCrossCorrelation()
        elif self.combobox.GetValue() == 'Auto Correlation C0':
            self.autocorrelationchannel = 0
            self.AutoCorrelation()
        elif self.combobox.GetValue() == 'Auto Correlation C1':
            self.autocorrelationchannel = 1
            self.AutoCorrelation()
        else:
            self.autocorrelationchannel = 2
            self.AutoCorrelation()
    
    def OnRunOnce(self,event):
        self.cumulativeflag = False
        self.timetags = self.HRMTime.TimeTags2Mem(self.ncounts,self.recordinglength)
        self.CalcCorrelation()
    
    def OnRunContinuous(self,event):
        #self.HRMTime.TimeTags2Mem(self.ncounts,self.recordinglength,esr=0); self.HRMTime.TimeTags2Mem(self.ncounts,self.recordinglength,esr=0xAAAA)
        #print "All channels off. Then all channels on."
        if self.DataCollectFlag:
            print 'WARNING: Already collecting data!!!'
        else:
            self.t0 = time.time()
            t = threading.Timer(0, function=self.CalcCorrelationContinuous)
            t.daemon = True
            t.start()
    
    def CalcCorrelationContinuous(self):
        self.DataCollectFlag = True
        self.cumulativeflag = False
        self.timetags = self.HRMTime.TimeTags2Mem(self.ncounts,self.recordinglength)
		
        self.CalcCorrelation()
        while self.DataCollectFlag:
            self.cumulativeflag = self.cumulativetickbox.GetValue()
            #self.autosaveflag = self.autosavetickbox.GetValue()
            self.timetags = self.HRMTime.TimeTags2Mem(self.ncounts,self.recordinglength)
            self.CalcCorrelation()
    
    def OnStop(self,event):
        self.DataCollectFlag = False
    
    def OnComboSelect(self,event):
        self.OnStop(None)
        self.ax.clear()
        self.canvas.draw()
    
    def OnApply(self,event):
        self.OnStop(None)
        self.recordinglength = int(self.rightpaneltextctrls[0].GetValue())
        self.ncounts = int(self.rightpaneltextctrls[1].GetValue())
        self.dtmax = int(self.rightpaneltextctrls[2].GetValue())
        self.plotbinfactor = int(self.rightpaneltextctrls[3].GetValue())
        self.dntags = int(self.rightpaneltextctrls[4].GetValue())
    
    def OnSaveCorrelation(self,event):
        #self.GetFilePath(filetype='.csv',dialoguetype='save')
        self.GetFilePath(dialoguetype='save')
        try:
            np.save(self.filepath+"Ch0thenCh1",np.array([self.correlation_x,self.correlation_hist]).transpose())
            np.save(self.filepath+"Ch0thenCh2",np.array([self.correlation_x2,self.correlation_hist2]).transpose())
            np.save(self.filepath+"Ch2thenCh1",np.array([self.correlation_x21,self.correlation_hist21]).transpose())
            np.save(self.filepath+"Ch0thenCh2thenCh1",np.array([self.correlation_x021, self.heralded_correlation_hist]).transpose())
            #np.save(self.filepath+"Ch0thenCh2thenCh1_gate2",np.array([self.correlation_x021_gate2, self.heralded_correlation_hist_gate2]).transpose())
            #np.save(self.filepath+"signal_times_ch1",self.signal_times_ch1)
            #np.save(self.filepath+"signal_times_ch2", self.signal_times_ch2)
            #np.save(self.filepath+"signal_times_ch1_gate2",self.signal_times_ch1_gate2)
            #np.save(self.filepath+"signal_times_ch2_gate2", self.signal_times_ch2_gate2)
            #np.save(self.filepath+"signal_times_ch1_gate3",self.signal_times_ch1_gate3)
            #np.save(self.filepath+"signal_times_ch2_gate3", self.signal_times_ch2_gate3)
            #np.save(self.filepath+"signal_times_ch1_gate4",self.signal_times_ch1_gate4)
            #np.save(self.filepath+"signal_times_ch2_gate4", self.signal_times_ch2_gate4)
            #np.save(self.filepath+"signal_times_ch1_gate5",self.signal_times_ch1_gate5)
            #np.save(self.filepath+"signal_times_ch2_gate5", self.signal_times_ch2_gate5)
            #np.save(self.filepath+"signal_times_ch1_gate6",self.signal_times_ch1_gate6)
            #np.save(self.filepath+"signal_times_ch2_gate6", self.signal_times_ch2_gate6)
            #np.save(self.filepath+"Ch0thenCh2thenCh1CRH",self.correlation_hist_CRH)
            
        except:
            print "not saved"
        if self.combobox.GetValue() == 'Cross Correlation':
            header = 'Integration time (s), Ch0 count rate (kHz), Ch1 count rate (kHz)'
            header2 = 'Time from start (s), Integration time (s), Ch0 count rate (kHz), Ch1 count rate (kHz), Ch2 count rate (kHz), Ch3 count rate (kHz)'
            np.savetxt(self.filepath+'-timed.txt',self.temp_output,header=header2,delimiter=',')
        elif self.combobox.GetValue() == 'Heralded Cross Correlation':
            header = 'Integration time (s), Ch0 count rate (kHz), Ch1 count rate (kHz), Ch2 count rate (kHz), Ch3 count rate (kHz)'
            
            np.savetxt(self.filepath+'-timed.txt',self.temp_output,header=header2,delimiter=',')
        elif self.combobox.GetValue() == 'Auto Correlation C0':
            header = 'Integration time (s), Ch0 count rate (kHz)'
        elif self.combobox.GetValue() == 'Auto Correlation C1':
            header = 'Integration time (s), Ch1 count rate (kHz)'
        else:
            header = 'Integration time (s), Ch2 count rate (kHz)'
        np.savetxt(self.filepath+'-info.txt',self.correlation_info,header=header,delimiter=',')
        # Save g(2) image on screen
        self.fig.savefig(self.filepath+'screenshot.png')
        
        channels,times = self.timetags[:,0],self.timetags[:,1] 
        np.save(self.filepath+"channels", channels)
        np.save(self.filepath+"timetags", times)
        np.savetxt(self.filepath+"dt_02s.csv", np.array(self.dt_02s))
        np.savetxt(self.filepath+"dt_21s.csv", np.array(self.dt_21s))
        np.save(self.filepath+"Ch2thenCh0",np.array([self.correlation_x20,self.correlation_hist20]).transpose())
        
        dataCh0thenCh2thenCh1 = np.array([self.correlation_x021, self.heralded_correlation_hist]).transpose()
        dataCh0thenCh1 = np.array([self.correlation_x,self.correlation_hist]).transpose()
        dataCh0thenCh2 = np.array([self.correlation_x2,self.correlation_hist2]).transpose()
                
        windowed_021_data = dataCh0thenCh2thenCh1[((dataCh0thenCh2thenCh1[:,0]>(self.lower_01-self.lower_02-self.width/2)) & (dataCh0thenCh2thenCh1[:,0]<(self.lower_01-self.lower_02+self.width/2))),:]
        counts_021 = np.sum(windowed_021_data[:,1])
        print('no. of 021 counts = ',counts_021)
                
        # 02 counts
        windowed_02_data = dataCh0thenCh2[((dataCh0thenCh2[:,0]>self.lower_02) & (dataCh0thenCh2[:,0]<self.higher_02)),:]
        counts_02 = np.sum(windowed_02_data[:,1])
        print('no. of 02 counts = ',counts_02)

        # 01 counts
        windowed_01_data = dataCh0thenCh1[((dataCh0thenCh1[:,0]>self.lower_01) & (dataCh0thenCh1[:,0]<self.higher_01)),:]
        counts_01 = np.sum(windowed_01_data[:,1])
        print('no. of 01 counts = ',counts_01)
                
        info = np.array(self.temp_output)
        Ch0_rate = np.average(info[:,2])*1000 
        print('Ch0 rate =',Ch0_rate)
        Ch0_int_time = info[-1,1]
        print('integration time = ',Ch0_int_time)
        Ch0_counts = Ch0_rate * Ch0_int_time
                
        g2 = counts_021 * Ch0_counts/(counts_01 * counts_02)
        print('g2 = ',g2)
        g2_error = np.sqrt(counts_021)/counts_021 * g2
        print('g2 error = ', g2_error)
                
        self.calculated_g2 = np.array([g2,g2_error, counts_021, counts_02, counts_01, Ch0_counts])  
        header3 = 'g2, g2_error, counts_021, counts_02, counts_01, Ch0_counts'                
        np.savetxt(self.filepath+'g2(0).txt',self.calculated_g2,header=header3,delimiter=',')
    
    def GetFilePath(self,filetype='.*',dialoguetype='open'):
        if dialoguetype=='open':
            dlg = wx.FileDialog(self, "Choose a file", self.dirname, '', '*'+filetype, wx.OPEN)
        else:
            #dlg = wx.FileDialog(self, "Choose a file", self.dirname, '', '*'+filetype, wx.SAVE|wx.OVERWRITE_PROMPT)
            dlg = wx.FileDialog(self, "Choose a file", self.dirname, '', '*'+filetype, wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            
        if dlg.ShowModal() == wx.ID_OK:
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            self.filepath = os.path.join(self.dirname, self.filename)
        dlg.Destroy()
    
    def CrossCorrelation(self):
        '''function which turns 'timetags', a 2D array of times of photon clicks and corresponding detector channel that the click was 
        registered on, into a histogram of timegaps between clicks on particular channels. 'timetags' is collected from the detector in CalcCorrelationContinuous'''
        # Set times used for coincidence window (in pico seconds)
        #coincidence_start = 6.4e3; coincidence_end = 7.5e3
        
        self.width = 1.5e3
        
        peak_02 = 5.9e3
        coincidence_start = peak_02-self.width/2; coincidence_end = peak_02+self.width/2 #1100uW of P780 
        self.lower_02 = coincidence_start; self.higher_02 = coincidence_end
        
        peak_01 = 36.8e3
        self.lower_01 = peak_01-self.width/2; self.higher_01 = peak_01+self.width/2 #1100uW of P780 
        
        
        herald_channel = 0; signal_channel = 1
        herald_channel2 = 0; signal_channel2 = 2

        # Store which channel clicks (0, 1 or 2) and the timetag for each click during a [~1 second] period
        channels,times = self.timetags[:,0],self.timetags[:,1] 
        
        # print "First timetag", times[0] ###
        binsize = 26.9851 
        nbins = int(self.dtmax/binsize + 1e-10) # Expect 1482 bins for dtmax = 40000 ps and binsize 26.9851 picoseconds
        dtmaxact = binsize*nbins
        # histogram resets in cumulative mode
        if self.cumulativeflag == False:
            self.correlation_hist = np.zeros(nbins)
            self.correlation_hist2 = np.zeros(nbins)
            self.correlation_hist21 = np.zeros(nbins) 
            self.correlation_hist20 = np.zeros(nbins)

            self.heralded_correlation_hist = np.zeros(nbins)

            self.temp_output = [] # To hold count rates at each timestep
            self.t0 = time.time() # time when run is started
            self.t1 = 0 # time when save happens
            self.counter = 0 # used to keep track of saves
            self.bigcounter = 0 # used to keep track of times around the loop
            self.dt_02s = []
            self.dt_21s = []
        print '----------------------------------------------------------------'
        
                
        for i in range(1,self.dntags+1):
            
            
            # Record the index at which there is a click on herald and the "subsequent" click is on signal
            # "Subsequent" is either "the next click" (i.e. i = 1) or "the click after the next" (i.e. i = 2) and so on...
            indices = np.arange(0,len(channels)-i,1,dtype=int)[(channels[:-i] == herald_channel) & (channels[i:] == signal_channel)] # i.e. indices01
            indices2 = np.arange(0,len(channels)-i,1,dtype=int)[(channels[:-i] == herald_channel2) & (channels[i:] == signal_channel2)] # i.e. indices02
            indices21 = np.arange(0,len(channels)-i,1,dtype=int)[(channels[:-i] == 2) & (channels[i:] == 1)]
            indices20 = np.arange(0,len(channels)-i,1,dtype=int)[(channels[:-i] == 2) & (channels[i:] == 0)]
            
            # timegaps are the time between "subsequent" clicks
            timegaps = times[indices+i]-times[indices]
            #timegaps = timegaps + 5000 #Add a delay to this channel
            
            timegaps2 = times[indices2+i]-times[indices2]
            #timegaps2 = timegaps2 + 10000 #Add a delay to this channel
            
            timegaps21 = times[indices21+i]-times[indices21]
            timegaps20 = times[indices20+i]-times[indices20]                                                 
            print str(i)+':', len(timegaps[timegaps<dtmaxact])
            
            # histogram data: x are the bin edges
            hist_i, x = np.histogram(timegaps,bins=nbins,range=(0,dtmaxact))
            hist_i2, x2 = np.histogram(timegaps2,bins=nbins,range=(0,dtmaxact))
            hist_i21, x21 = np.histogram(timegaps21,bins=nbins,range=(0,dtmaxact))
            self.correlation_hist += hist_i
            self.correlation_hist2 += hist_i2   
            self.correlation_hist21 += hist_i21
            hist_i20, x20 = np.histogram(timegaps20,bins=nbins,range=(0,dtmaxact))
            self.correlation_hist20 += hist_i20                                                                       
			
            for j in range(1,4):
                indices_all = np.arange(0,len(channels)-i-j,dtype=int)[(channels[0:-i-j] == 0) & (channels[i:-j] == 2) & (channels[i+j:] == 1)]
                dt_02 = times[indices_all+i]-times[indices_all]
                indices = indices_all[(dt_02>coincidence_start)&(dt_02<coincidence_end)]
                dt_02 = times[indices+i]-times[indices]
                self.dt_02s.extend(dt_02)
                dt_21 = times[indices+i+j]-times[indices+i]
                self.dt_21s.extend(dt_21)
                
                hist_ij, x = np.histogram(dt_21,bins=nbins,range=(0,dtmaxact))
                

                self.heralded_correlation_hist += hist_ij

                #print "i",i,"j",j, sum(self.heralded_correlation_hist)
                #print self.dt_02s
        # Ensures that leftmost bin starts at t = 0    
        self.correlation_x = x[:-1]+(binsize/2) 
        self.correlation_x2 = x2[:-1]+(binsize/2) 
        self.correlation_x21 = x21[:-1]+(binsize/2)  
        self.correlation_x20 = x20[:-1]+(binsize/2) # Ensures that leftmost bin starts at t = 0                                                                                        
        self.correlation_x021 = x[:-1]+(binsize/2) 

        
        # info contains integration time, ch0 count rate, ch1 count rate, ch2 count rate, ch3 count rate
        # averages in cumulative mode
        if self.cumulativeflag == False:
            #### Be careful not to have such a low count rate that this no longer gives an accurate integration time
            self.inttime = times[-1]/1e12
            self.ncounts_ch0 = len(channels[channels==0])
            self.ncounts_ch1 = len(channels[channels==1])
            self.ncounts_ch2 = len(channels[channels==2])
            self.ncounts_ch3 = len(channels[channels==3])
            #try:
            #    np.savetxt('delete.csv',np.array([channels,times]).transpose(),delimiter=',')
            #except:
            #    print "couldn't save"

        else:
            #### Be careful not to have such a low count rate that this no longer gives an accurate integration time
            self.inttime += times[-1]/1e12
            self.ncounts_ch0 += len(channels[channels==0])
            self.ncounts_ch1 += len(channels[channels==1])
            self.ncounts_ch2 += len(channels[channels==2])
            self.ncounts_ch2 += len(channels[channels==3])
        # print 'Number of bins', nbins #1482 bins expected for 40 ns window
        print '------------------------------------------'
        print '--  Integration time =', times[-1]/1e12, 's '
        print '--  Ch0 count rate =', len(channels[channels==0])*1e9/times[-1], 'kHz  '
        print '--  Ch1 count rate =', len(channels[channels==1])*1e9/times[-1], 'kHz  '
        print '--  Ch2 count rate =', len(channels[channels==2])*1e9/times[-1], 'kHz  '
        print '--  Ch3 count rate =', len(channels[channels==3])*1e9/times[-1], 'kHz  '
        print '------------------------------------------'

        # Record the count rate at each timestep
        self.corr_info = [self.inttime,len(channels[channels==0])*1e9/times[-1],len(channels[channels==1])*1e9/times[-1],len(channels[channels==2])*1e9/times[-1],len(channels[channels==3])*1e9/times[-1]]
        self.t1 = time.time()
        self.t_elapsed = self.t1 - self.t0
        self.temp_output.append([self.t_elapsed, self.corr_info[0], self.corr_info[1], self.corr_info[2], self.corr_info[3], self.corr_info[4]])
   
        # info contains integration time, ch0 count rate, ch1 count rate, ch2 count rate, ch3 count rate (and later g2max and pair rate)
        self.correlation_info = [self.inttime,self.ncounts_ch0*1e-3/self.inttime,self.ncounts_ch1*1e-3/self.inttime,self.ncounts_ch2*1e-3/self.inttime,self.ncounts_ch3*1e-3/self.inttime]
        
        ########## Calculate and print statistics ###########
        normfactor = binsize*1e-12*self.correlation_info[0]*self.correlation_info[1]*1e3*self.correlation_info[2]*1e3
        normfactor2 = binsize*1e-12*self.correlation_info[0]*self.correlation_info[1]*1e3*self.correlation_info[3]*1e3
        normfactor20 = binsize*1e-12*self.correlation_info[0]*self.correlation_info[3]*1e3*self.correlation_info[1]*1e3
        normfactor21 = binsize*1e-12*self.correlation_info[0]*self.correlation_info[2]*1e3*self.correlation_info[3]*1e3
        
        nbins = len(self.correlation_hist)
        nbins2 = len(self.correlation_hist2)
        ncor_uncorrected = sum(self.correlation_hist) # Coincidence rate (RSM)
        ncor_uncorrected2 = sum(self.correlation_hist2) # Coincidence rate (RSM)
        ncor = sum(self.correlation_hist)-normfactor*nbins # Pair rate between herald and signal1
        ncor2 = sum(self.correlation_hist2)-normfactor2*nbins # Pair rate between herald and signal2
        
        print 'Calculating correlation between Ch0 (herald) and Ch1 (signal)'
        print 'Total Integration time             =', self.correlation_info[0], 's'
        print 'Ch0 average count rate             =', self.correlation_info[1], 'kHz'
        print 'Ch1 average count rate             =', self.correlation_info[2], 'kHz'
        print 'Ch2 average count rate             =', self.correlation_info[3], 'kHz'
        print 'Ch3 average count rate             =', self.correlation_info[4], 'kHz'
        print 'Pair count rate (uncorrected)      =', ncor_uncorrected/self.correlation_info[0], 'Hz'
        print 'Pair count rate (corrected  )      =', ncor/self.correlation_info[0], 'Hz'
        print 'Pair count rate 2 (corrected  )      =', ncor2/self.correlation_info[0], 'Hz'
        print 'Heralding efficiency (uncorrected) =', ncor_uncorrected/(self.correlation_info[0]*self.correlation_info[1]*1e3)
        print 'Heralding efficiency (corrected  ) =', ncor/(self.correlation_info[0]*self.correlation_info[1]*1e3)
        print ''
        

            
            
        ########### Plot cross correlation vs. time delay #############
        self.ax.clear()
        
        self.ax.tick_params(axis='both', which='both', bottom=True)
        self.ax.set_xlabel('Delay (ns)')
        self.ax.set_ylabel('Normalised Cross Correlation')

        x,y = bindata(self.correlation_x,self.correlation_hist,self.plotbinfactor)
        x2,y2 = bindata(self.correlation_x2,self.correlation_hist2,self.plotbinfactor)
        x21,y21 = bindata(self.correlation_x21,self.correlation_hist21,self.plotbinfactor)
        x021,y021 = bindata(self.correlation_x021,self.heralded_correlation_hist,self.plotbinfactor)#
        x20,y20 = bindata(self.correlation_x20,self.correlation_hist20,self.plotbinfactor)
        self.ax.plot(x/1e3,y/(normfactor*2**self.plotbinfactor), color = 'red')   #Ch0 then Ch1 
        self.ax.plot(x2/1e3,y2/(normfactor2*2**self.plotbinfactor), color = 'blue') #Ch0 then Ch2
        self.ax.plot(x21/1e3,y21/(normfactor21*2**self.plotbinfactor), color = 'green') #Ch2 then Ch1
        #self.ax.plot(x20/1e3,y20/(normfactor20*2**self.plotbinfactor), color = 'purple')   #Ch2 then Ch0
        self.ax.plot(x021/1e3,y021/(normfactor21*2**self.plotbinfactor), color = 'orange')#Ch0 then Ch2 then Ch1
        self.canvas.draw() 
   
        print "We expect red g2max at:", peak_01/1e3
        print "At this time we get red g2max:", (x[np.argmax(y)]/1e3)
        print "Red g2max = ", (y/(normfactor*2**self.plotbinfactor)).max()
        
        print "We expect blue g2max at:", peak_02/1e3
        print "At this time we get blue g2max:", (x2[np.argmax(y2)]/1e3)
        print "Blue g2max = ", (y2/(normfactor2*2**self.plotbinfactor)).max()
        
        
        self.correlation_info.append((y/(normfactor*2**self.plotbinfactor)).max()) # Add g2_max to self.correlation_info which will be saved in data-info.txt
        self.correlation_info.append(ncor/self.correlation_info[0]) # Add pair-rate to self.correlation_info which will be saved as data-info
        
        #### Autosave if the instantaneous count rate drops below a certain value ####
        inst_Ch0_countrate = len(channels[channels==0])*1e9/times[-1]
        if (self.autosaveflag == True) and (inst_Ch0_countrate < self.autosaverate):
            print "Warning: Ch1 count rate dropped below", self.autosaverate, " kHz,", inst_Ch0_countrate, "Hz"  
            import datetime; currentDT = datetime.datetime.now()            
            self.AutoSave()
            print "Autosaved"
            print "Autostopped at", currentDT
        
        #### Autosave at regular intervals ###
        self.bigcounter += 1       
        if self.bigcounter % (200*3) == 0: #Every 200 times around the loop is ~4 mins
            if self.counter == 0: 
                self.counter += 1
            else:
                
                directoryname = "shot"+str(self.counter)
                print "Going to autosave after seconds:", int(time.time()-self.t0)
                
                filepath = os.getcwd()+"\\"+directoryname
                print "Now we will autosave to:", filepath

                if os.path.isdir(filepath) == False: os.mkdir(filepath)
                np.save(filepath+"\\dataCh0thenCh1",np.array([self.correlation_x,self.correlation_hist]).transpose())
                np.save(filepath+"\\dataCh0thenCh2",np.array([self.correlation_x2,self.correlation_hist2]).transpose())
                np.save(filepath+"\\dataCh2thenCh1",np.array([self.correlation_x21,self.correlation_hist21]).transpose())
                np.save(filepath+"\\dataCh0thenCh2thenCh1",np.array([self.correlation_x021, self.heralded_correlation_hist]).transpose())
                np.save(filepath+"\\dataCh2thenCh0",np.array([self.correlation_x20,self.correlation_hist20]).transpose())
                header = 'Integration time (s), Ch0 count rate (kHz), Ch1 count rate (kHz), Ch2 count rate (kHz), Ch3 count rate (kHz), g2_max_red_curve, pair-rate (Hz'
                header2 = 'Time from start (s), Integration time (s), Ch0 count rate (kHz), Ch1 count rate (kHz), Ch2 count rate (kHz), Ch3 count rate (kHz)'
                np.savetxt(filepath+'\\data-timed.txt',self.temp_output,header=header2,delimiter=',')
                np.savetxt(filepath+'\\data-info.txt',self.correlation_info,header=header,delimiter=',')
                self.fig.savefig(filepath+'\\screenshot.png')# Save g(2) image on screen
                channels,times = self.timetags[:,0],self.timetags[:,1] 
                np.save(filepath+"\\datachannels", channels)
                np.save(filepath+"\\datatimetags", times)
                np.savetxt(filepath+"\\dt_02s.csv", np.array(self.dt_02s))
                np.savetxt(filepath+"\\dt_21s.csv", np.array(self.dt_21s))
                
                dataCh0thenCh2thenCh1 = np.array([self.correlation_x021, self.heralded_correlation_hist]).transpose()
                dataCh0thenCh1 = np.array([self.correlation_x,self.correlation_hist]).transpose()
                dataCh0thenCh2 = np.array([self.correlation_x2,self.correlation_hist2]).transpose()
                
                windowed_021_data = dataCh0thenCh2thenCh1[((dataCh0thenCh2thenCh1[:,0]>(self.lower_01-self.lower_02-self.width/2)) & (dataCh0thenCh2thenCh1[:,0]<(self.lower_01-self.lower_02+self.width/2))),:]
                counts_021 = np.sum(windowed_021_data[:,1])
                print('no. of 021 counts = ',counts_021)
                
                # 02 counts
                windowed_02_data = dataCh0thenCh2[((dataCh0thenCh2[:,0]>self.lower_02) & (dataCh0thenCh2[:,0]<self.higher_02)),:]
                counts_02 = np.sum(windowed_02_data[:,1])
                print('no. of 02 counts = ',counts_02)

                # 01 counts
                windowed_01_data = dataCh0thenCh1[((dataCh0thenCh1[:,0]>self.lower_01) & (dataCh0thenCh1[:,0]<self.higher_01)),:]
                counts_01 = np.sum(windowed_01_data[:,1])
                print('no. of 01 counts = ',counts_01)
                
                info = np.array(self.temp_output)
                Ch0_rate = np.average(info[:,2])*1000 
                print('Ch0 rate =',Ch0_rate)
                Ch0_int_time = info[-1,1]
                print('integration time = ',Ch0_int_time)
                Ch0_counts = Ch0_rate * Ch0_int_time
                
                g2 = counts_021 * Ch0_counts/(counts_01 * counts_02)
                print('g2 = ',g2)
                g2_error = np.sqrt(counts_021)/counts_021 * g2
                print('g2 error = ', g2_error)
                
                self.calculated_g2 = np.array([g2,g2_error, counts_021, counts_02, counts_01, Ch0_counts])  
                header3 = 'g2, g2_error, counts_021, counts_02, counts_01, Ch0_counts'                
                np.savetxt(filepath+'\\g2(0).txt',self.calculated_g2,header=header3,delimiter=',')
                
                #raw_input("Press Enter to continue...")
                self.counter += 1

            
    def AutoSave(self):
        print "Going to autosave..."
        filepath = os.getcwd()+"\\data"
        if os.path.isdir(filepath) == False: os.mkdir(filepath)
        np.save(filepath+"\\dataCh0thenCh1",np.array([self.correlation_x,self.correlation_hist]).transpose())
        np.save(filepath+"\\dataCh0thenCh2",np.array([self.correlation_x2,self.correlation_hist2]).transpose())
        np.save(filepath+"\\dataCh2thenCh1",np.array([self.correlation_x21,self.correlation_hist21]).transpose())
        np.save(filepath+"\\dataCh0thenCh2thenCh1",np.array([self.correlation_x021, self.heralded_correlation_hist]).transpose())
        header = 'Integration time (s), Ch0 count rate (kHz), Ch1 count rate (kHz), Ch2 count rate (kHz), Ch3 count rate (kHz)'
        header2 = 'Time from start (s), Integration time (s), Ch0 count rate (kHz), Ch1 count rate (kHz), Ch2 count rate (kHz), Ch3 count rate (kHz)'
        np.savetxt(filepath+'\\data-timed.txt',self.temp_output,header=header2,delimiter=',')
        np.savetxt(filepath+'\\data-info.txt',self.correlation_info,header=header,delimiter=',')
        self.fig.savefig(filepath+'\\screenshot.png') # Save g(2) image on screen
        self.DataCollectFlag = False 
        channels,times = self.timetags[:,0],self.timetags[:,1] 
        np.save(filepath+"\\datachannels", channels)
        np.save(filepath+"\\datatimetags", times)
        np.savetxt(filepath+"\\dt_02s.csv", np.array(self.dt_02s))
        np.savetxt(filepath+"\\dt_21s.csv", np.array(self.dt_21s))
        
        

        
if __name__ == "__main__":
    print "Looks at: 01-02-21-021gated-normalised"
    print "i.e. Ch0-then-Ch1; Ch0-then-Ch2; Ch2-then-Ch1; Ch0-then-Ch2-then-Ch1,but-within-a-specified-time-window"
    app = wx.App(False)
    mainframe = MainFrame(None, "correlator.py")
    app.MainLoop()
