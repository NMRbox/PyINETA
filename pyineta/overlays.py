import numpy as np
import matplotlib.pyplot as plt
import re
import operator
import nmrglue as ng
import pyineta.plotting as plotting

def readFt (ftfile):
	"""Read ft files using nmrglue.

	Args:
		ftfile (str): ft filename.

	Returns:
		ndarray : A numpy array with the intensities.
		1D-array : A 1D array with the 13C ppm values.
		1D-array : A 1D array with the double quantum ppm values.
	"""

	ft_dic,ft_data = ng.pipe.read(ftfile)
	In=ft_data.transpose()

	DQ = ng.pipe.make_uc(ft_dic, ft_data, 0)
	Ys=DQ.ppm_scale()

	CS = ng.pipe.make_uc(ft_dic, ft_data, 1)
	Xs=CS.ppm_scale()
	return(In,Xs,Ys)

def read1D (ftfile1D):
    ft_dic,ft_data = ng.pipe.read(ftfile1D)
    CS = ng.pipe.make_uc(ft_dic, ft_data, 0)
    if ft_data.dtype=='complex64':
        data_e1 = np.stack([np.real(ft_data), np.imag(ft_data)], axis=-1)
        ft_data=data_e1[:,0]
    Xs=CS.ppm_scale()
    return(ft_data,Xs)

def shift1D (In,pX,fullX,direction):
    # print(In)
    if direction.lower() == "pos":      # For increasing ppm axes (eg: peak at 35 ppm is now at 40 ppm)
        padX=np.zeros(pX)   # fullY= 8192 for INADEQUATE
        In=np.concatenate((In,padX))
        In=In[pX:]
    elif direction.lower() == "neg":        # For decreasing ppm axes (eg: peak at 40 ppm is now at 35 ppm)
        padX=np.zeros(pX)   # fullY= 8192 for INADEQUATE
        In=np.concatenate((padX,In))
        In=In[:-pX]
    # print(In)
    return(In)

def readJres (ftfileJres):
    ft_dic,ft_data = ng.pipe.read(ftfileJres)
    print("****")
    print(ft_dic)
    print("****")
    print(ft_data.shape)
    In=ft_data.transpose()
    
    DQ = ng.pipe.make_uc(ft_dic, ft_data, 0)
    Ys=DQ.ppm_scale()

    CS = ng.pipe.make_uc(ft_dic, ft_data, 1)
    Xs=CS.ppm_scale()
    return(In,Xs,Ys)

def writeOverlays (filelist,aucfile,intThres,outfilename):    
    out_file = open(outfilename, 'w')
    for entry in aucfile:
        outline=entry
        for num in aucfile[entry]:
            outline+="\t"+filelist[num]+"="
            for i in aucfile[entry][num]:
                if (i[3]>=intThres):
                    met="Present"
                else:
                    met="Absent"
                outline+=i[0]+"["+met+"]("+str(i[1])+","+str(i[2])+")"+":"+str(i[3])+";"
        outline+='\n'
        out_file.write(outline)

def overlay1D (pyinetaObj,files1D,ptsTol,aucTol,intThres,outfilename,outimgname,net,shift=None):
    filelist=files1D.split(',')
    nrows = len(filelist)
    allAUC=dict()
    fig_net=dict()
    ax_net=dict()
    ct=dict()
    fig, axs = plt.subplots(nrows, 1, figsize=(30, nrows*5), sharex=True)
    for j,filename in enumerate(filelist):
        fn=filename.split("/")[-1].rsplit(".",1)[0]
        # Reading 1D file
        (In,Xs)=read1D(filename)
        # Matching networks to 1D peaks
        if shift is not None:
            if type(shift) is list and len(shift)==3:
                if (shift[2].lower() == 'pos'):
                    directionShift="higher"
                else:
                    directionShift="lower"
                ppmUnits=(200/shift[1])*shift[0]
                print("\nStep5.1==>Shifting 1D spectra to %s ppm level by %.2f units (%.2f ppm on 13C axis)" % (directionShift,shift[0],ppmUnits))
                In=shift1D(In,*shift)
            else:
                exit("ERROR: Argument shift needs to be a list with 3 items:padding units, total size of X axis and direction (either pos or neg). Eg: [20,4096,'pos']")

        aucregion=dict()
        for Net in pyinetaObj.NetMatch:
            if Net[0] not in allAUC:
                allAUC[Net[0]]=dict()
            allAUC[Net[0]][j]=list()
            Matched=np.zeros(1)
            arr=np.around(np.asarray(Net[1]),decimals=2)
            arr2=np.around(np.asarray(Net[2]),decimals=2)
            aucregion[Net[0]]=list()
            for i,Pt in enumerate(arr):
                if np.isclose(Matched,Pt,atol=ptsTol).any():
                    continue
                Matched=np.append(Matched,Pt)
                valMin=Pt-aucTol/2
                valMax=Pt+aucTol/2
                idxMin = (np.abs(Xs - valMin)).argmin()
                idxMax = (np.abs(Xs - valMax)).argmin()
                indices=[idxMin,idxMax]
                auc=In[indices].sum()
                allAUC[Net[0]][j].append([Net[3][i],Pt,arr2[i],auc])
                aucregion[Net[0]].append((valMin,valMax))
        # Plotting overall 1D plots
        if isinstance(axs,np.ndarray):
            currax=axs[j]
        else:
            currax=axs
        # print(In.shape)
        plotting.plot1D(In,Xs,aucregion,ax=currax,title=fn,net=net)
        auc_lower = {k.lower():v for k,v in aucregion.items()}
        # Plotting individual matched regions for specified networks
        print("Plotting individual network matches for %s ..." % (fn))
        if net is None:
            Netlist=[item[0].lower() for item in pyinetaObj.NetMatch]
        else:
            Netlist=net.lower().split(",")
        for n in Netlist:
            ncols=len(auc_lower[n])
            if n not in fig_net:
                fig_net[n],ax_net[n] = plt.subplots(nrows, ncols, figsize=(ncols*5, nrows*5))
                ct[n]=0
            auc_lower[n].sort(key = operator.itemgetter(0), reverse = True)
            for k,r in enumerate(auc_lower[n]):
                # print(n,nrows,ncols)
                # print(ax_net[n].ndim)
                if (ncols>1):
                    if isinstance(ax_net[n][j],np.ndarray):
                        curr_ax=ax_net[n][j][k]
                    else:
                        curr_ax=ax_net[n][j]
                else:
                    curr_ax=ax_net[n]
                curr_ax.plot(Xs,In,'k-')
                low_lim=r[0]-1
                up_lim=r[1]+1
                curr_ax.axvspan(r[0], r[1], facecolor='g', alpha=0.1)
                curr_ax.set_xlim(low_lim,up_lim)
                midpt=(r[0]+r[1])/2
                title=fn+" "+str(r[0])+"-"+str(r[1])+"("+str(midpt)+")"
                curr_ax.set_title(title)
                curr_ax.invert_xaxis()
                ct[n]+=1
    # Save individual peak stacks for specified networks (-n flag)    
    for n in fig_net:
        outcurrimg=outimgname.rsplit(".",1)[0]+"_"+n+".svg"
        fig_net[n].tight_layout()
        fig_net[n].savefig(outcurrimg)
    # Write 1D matches for all networks to a file
    writeOverlays(filelist,allAUC,intThres,outfilename)
    # Save final figure
    if isinstance(ax_net[n][j],np.ndarray):
        curr_ax=axs[0]
    else:
        curr_ax=axs
    curr_ax.invert_xaxis()
    lines, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(lines, labels, loc = 'upper right')
    fig.tight_layout()
    fig.savefig(outimgname)

def overlayJres (pyinetaObj,filesJres):
    filelist=filesJres.split(',')
    allAUC=dict()
    fig, axs = plt.subplots(len(filelist), 1, figsize=(30, 10), sharex=True)
    for j,filename in enumerate(filelist):
        # Reading 1D file
        (In,Xs,Ys)=readJres(filename)
        print(In,Xs,Ys)
        print(In.shape)
        print(Xs.shape)
        print(Ys.shape)
        print("---------")
        print(pyinetaObj.In,pyinetaObj.Cppm,pyinetaObj.DQppm)
        
