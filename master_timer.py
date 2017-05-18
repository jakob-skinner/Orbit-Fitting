#import-libraries-and-data---------------------------------------------------------------------------------------#
import sys, os, numpy as np, functions as f
#from scipy import stats
from matplotlib import pyplot as plt, rcParams
rcParams.update({'figure.autolayout' : True})
file     = 'Systems/3325.txt'
data       = np.genfromtxt(file, skip_header=1, usecols=(0, 1, 3))
system         = list(file)

# the string manipulations below extract the 2MASS ID from the file name
while system[0] != '2' and system[1] != 'M':
    del system[0]
while system[-1] != '.':
    del system[-1]
del system[-1]
system = ''.join(system)

#define-variables------------------------------------------------------------------------------------------------#

JD, RVp, RVs    = [datum[0] for datum in data], [datum[1] for datum in data], [datum[2] for datum in data]
JDp, JDs        = JD, JD
samples         = 1000
max_period      = 5
nwalkers, nsteps= 100 ,4000
threads         = 4

#define-functions------------------------------------------------------------------------------------------------#

periodogram, dataWindow, maxima, phases, massRatio = f.periodogram, f.dataWindow, f.maxima, f.phases, f.massRatio
adjustment, RV, residuals, MCMC, lowEFit = f.adjustment, f.RV, f.residuals, f.MCMC, f.lowEFit

#now-do-things!--------------------------------------------------------------------------------------------------#

#plot Wilson plot (mass ratio)
mass_ratio, intercept, r_squared, standard_error, slope_error = massRatio(RVs,RVp, data)
gamma = intercept/(1+mass_ratio)

fig = plt.figure(figsize=(5,5))
ax = plt.subplot(111)
ax.plot(RVs, RVp, 'k.')
x, y = np.array([np.nanmin(RVs), np.nanmax(RVs)]),-mass_ratio*np.array([np.nanmin(RVs), 
                                                                        np.nanmax(RVs)])+intercept
ax.plot(x, y)
ax.set_title(system)
ax.text(0, 20, 'q = %s $\pm$ %s\n$\gamma$ = %s $\\frac{km}{s}$' %(np.round(mass_ratio, decimals = 3), np.round(standard_error, decimals = 3),
                                                     np.round(gamma, decimals = 3)))
ax.set_ylabel('Primary Velocity (km/s)')#, size='15')
ax.set_xlabel('Secondary Velocity (km/s)')#, size='15')
#plt.savefig(file + ' mass ratio.png')
#plt.show()

#check for invalid values
JDp, RVp = adjustment(JD, RVp)
JDs, RVs = adjustment(JD, RVs)


#calculate periodograms
x, y, delta_x  = periodogram(JDp, RVp, samples, max_period)

y2    = periodogram(JDs, RVs, samples, max_period)[1]
y3,y4 = dataWindow(JDp, samples, max_period)[1], dataWindow(JDs, samples, max_period)[1]

#plot periodograms
#fig, ((ax1,ax4),(ax2,ax5),(ax3,ax6)) = plt.subplots(3, 2, sharex='col', sharey='row')
#ax1.plot(x, y, 'k')
#ax1.set_title('Periodograms: Primary')
#ax1.set_xlim(1/24, max_period)
#ax4.set_xlim(1/24, max_period)
#ax2.plot(x, y2, 'k')
#ax2.set_title('Secondary')
#ax3.plot(x, y*y2, 'k')
#ax3.set_title('Product Periodogram')
#ax4.plot(x, y3, 'k')
#ax4.set_title('Primary Data Window')
#ax5.plot(x, y4, 'k')
#ax5.set_title('Secondary Data Window')
#ax6.plot(x, y3*y4, 'k')
#ax6.set_title('Product Data Window')
#ax3.set_xlabel('Period (days)', size='15')
#ax6.set_xlabel('Period (days)', size='15')
#ax2.set_ylabel('Normalized Lomb-Scargle Power', size='20')
#fig.set_figheight(10)
#fig.set_figwidth(15)
#plt.savefig(file + 'periodogram.png')


#plot periodogram - data window
fig = plt.figure(figsize=(8,3))
ax = plt.subplot(111)
ax.plot(x, y*y2-y3*y4, 'k', alpha = 1)
ax.plot(x, y*y2, 'b', alpha = 0.5)
ax.plot(x, y3*y4, 'r', alpha = 0.5)
ax.set_ylabel('Periodogram Power')#, size='15')
ax.set_xlabel('Period (days)')#, size='15')
ax.set_ylim(0,1)
ax.set_xlim(delta_x,max_period)
ax.set_title(system)
#plt.savefig(file + ' adjusted periodogram.png')
#plt.show()

#-----------------------MCMC------------------------#
import time

for i in range(600):
    start = time.time() #start timer
    #constrain parameters
    lower_bounds = [0, -1, 0, np.median(np.asarray(JD))-0.5*max_period, delta_x, min(min(RVs), min(RVp))]
    upper_bounds = [200, 1, 2*np.pi, np.median(np.asarray(JD))+0.5*max_period, max_period, max(max(RVs), max(RVp))]

    #take a walk
    sampler = MCMC(mass_ratio, gamma, RVp, RVs, JDp, JDs, lower_bounds, upper_bounds, 6, nwalkers, nsteps, threads)

    #save the results of the walk
    samples = sampler.chain[:, 2000:, :].reshape((-1, 6))
    results = np.asarray(list(map(lambda v: (v[1], v[2]-v[1], v[1]-v[0]),
                                zip(*np.percentile(samples, [16, 50, 84], axis=0)))))
    parameters = [0,0,0,0,0,0]
    for i in range(6):
        parameters[i] = results[i][0]

    #Adjust T
    T_sampler = lowEFit(mass_ratio, RVp, RVs, JDp, JDs, lower_bounds, upper_bounds, nwalkers, nsteps, threads, parameters)

    #save the results of the adjustment
    T_samples = T_sampler.chain[:, 2000:, :].reshape((-1, 1))
    T_results = np.asarray(list(map(lambda v: (v[1], v[2]-v[1], v[1]-v[0]),
                                    zip(*np.percentile(T_samples, [16, 50, 84], axis=0)))))
    results[3], parameters[3] = T_results, T_results[0]

    #if the eccentricity is negative, perform a transformation of the parameters to make it positive
    #add pi to longitude of periastron, and advance time of periastron by period/2
    if results[1][0] < 0:
        results[1][0], results[2][0], results[3][0] = -results[1][0], results[2][0] + np.pi, results[3][0] + results[4][0]/2
        results[1][1], results[1][2] = results[1][2], results[1][1] #swap uncertainties of e
    results[2] = results[2] * 180/np.pi #convert longtitude of periastron reporting from radians to degrees
    
    #end timer
    end = time.time()
    elapsed = end-start
    table = open('timer.txt', 'a+')
    print(nwalkers, ',', elapsed)
    print(nwalkers, ',', elapsed, file = table)
    nwalkers += 2
    table.close()