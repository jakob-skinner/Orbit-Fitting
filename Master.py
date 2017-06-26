#import-libraries-and-data---------------------------------------------------------------------------------------#
import os, numpy as np, functions as f

from matplotlib import pyplot as plt, rcParams
rcParams.update({'figure.autolayout' : True})
file     = 'Systems/1226+2439/2M12260848+2439315.tbl'
data       = np.genfromtxt(file, skip_header=1, usecols=(1, 2, 3))
system         = list(file)

# the string manipulations below extract the 2MASS ID from the file name
# while system[0] != '2' and system[1] != 'M':
#    del system[0]
while system[-1] != '.':
    del system[-1]
del system[-1]
system = ''.join(system)

#define-variables------------------------------------------------------------------------------------------------#

JD, RVp, RVs    = [datum[0] for datum in data], [datum[1] for datum in data], [datum[2] for datum in data]
JDp, JDs        = JD, JD
samples         = 10000
max_period      = 10
nwalkers, nsteps= 1000, 20000 #minimum nwalker: 14, minimum nsteps determined by the convergence cutoff
cutoff          = 5000

#define-functions------------------------------------------------------------------------------------------------#

periodogram, dataWindow, phases, wilson, kernelDensityP = f.periodogram, f.dataWindow, f.phases, f.wilson, f.kernelDensityP
adjustment, RV, residuals, MCMC, lowEFit, walkers, corner = f.adjustment, f.RV, f.residuals, f.MCMC, f.lowEFit, f.walkers, f.corner

#now-do-things!--------------------------------------------------------------------------------------------------#

#plot Wilson plot (mass ratio)
mass_ratio, intercept, standard_error = wilson(data)
gamma = intercept/(1+mass_ratio)

fig = plt.figure(figsize=(5,5))
ax = plt.subplot(111)
ax.plot(RVs, RVp, 'k.')

x, y = np.array([np.nanmin(RVs), np.nanmax(RVs)]),-mass_ratio*np.array([np.nanmin(RVs),np.nanmax(RVs)])+intercept

ax.plot(x, y)
#ax.set_title('Wilson plot for 2M17204248+4205070')
ax.text(30, 30, 'q = %s $\pm$ %s\n$\gamma$ = %s $\\frac{km}{s}$' %(round(mass_ratio, 3), round(standard_error, 3),
                                                     round(gamma, 3)))
ax.set_ylabel('Primary Velocity (km/s)')#, size='15')
ax.set_xlabel('Secondary Velocity (km/s)')#, size='15')
plt.savefig(file + ' mass ratio.png')
#plt.show()

#check for invalid values
JDp, RVp = adjustment(JD, RVp)
JDs, RVs = adjustment(JD, RVs)


#calculate periodograms
x, y, delta_x  = periodogram(JDp, RVp, samples, max_period)

y2    = periodogram(JDs, RVs, samples, max_period)[1]
y3,y4 = dataWindow(JDp, samples, max_period)[1], dataWindow(JDs, samples, max_period)[1]

#plot periodogram - data window
fig = plt.figure(figsize=(8,3))
ax = plt.subplot(111)
ax.plot(x, y*y2, 'b', alpha = 0.5)
ax.plot(x, y3*y4, 'r', alpha = 0.5)
ax.plot(x, y*y2-y3*y4, 'k', alpha = 1)
ax.set_ylabel('Periodogram Power')#, size='15')
ax.set_xlabel('Period (days)')#, size='15')
ax.set_ylim(0,1)
ax.set_xlim(delta_x,max_period)
ax.set_title(system)
plt.savefig(file + ' adjusted periodogram.png')
#plt.show()

#-----------------------MCMC------------------------#

import time

start = time.time() #start timer

#constrain parameters
lower_bounds = [0, 0, -1.6, np.median(np.asarray(JD))-0.5*max_period, 5.8, min(min(RVs), min(RVp))]
upper_bounds = [100, 0.9, 2*np.pi, np.median(np.asarray(JD))+0.5*max_period, 6.5, max(max(RVs), max(RVp))]

#take a walk
sampler = MCMC(mass_ratio, gamma, RVp, RVs, JDp, JDs, lower_bounds, upper_bounds, 6, nwalkers, nsteps, 4)
print('Walk complete.')

#save the results of the walk
samples = sampler.chain[:, cutoff:, :].reshape((-1, 6))
             

#calculate the parameter values and uncertainties from the quantiles
results = np.asarray(list(map(lambda v: (v[1], v[2]-v[1], v[1]-v[0]),
                              zip(*np.percentile(samples, [16, 50, 84], axis=0)))))


results = np.transpose(results)
results[0] = kernelDensityP(samples)
results = np.transpose(results)
print('Estimation complete.')

#create walkers plot
walkers(nsteps, 6, sampler, results).savefig(file + ' %s dimension walk results.png'%(6))

del sampler

#Adjust T
T_sampler = lowEFit(mass_ratio, RVp, RVs, JDp, JDs, lower_bounds, upper_bounds, nwalkers, nsteps, 4, np.transpose(results)[0])

#save the results of the adjustment
T_samples = T_sampler.chain[:, cutoff:, :].reshape((-1, 1))

T_results = np.asarray(list(map(lambda v: (v[1], v[2]-v[1], v[1]-v[0]),
                                zip(*np.percentile(T_samples, [16, 50, 84], axis=0)))))

results[3][0], results[3][1], results[3][2] = kernelDensityP(T_samples)[0], T_results[0][1], T_results[0][2]

samples = np.transpose(samples)
samples[3] = np.transpose(T_samples)
samples = np.transpose(samples)
print('T adjustment complete.')

mask = np.array([])
for i in range(samples.shape[0]):
    for j in range(6):
        if samples[i][j] < lower_bounds[j] or samples[i][j] > upper_bounds[j]:
            mask = np.append(mask, i)
samples = np.delete(samples, mask, 0)

del T_sampler, T_samples


#commented out since it was causing unnecessary issues with the interpretation of the walk. It is still valid
#if the eccentricity is negative, perform a transformation of the parameters to make it positive
#add pi to longitude of periastron, and advance time of periastron by period/2
#if results[1][0] < 0:
#    results[1][0], results[2][0], results[3][0] = -results[1][0], results[2][0] + np.pi, results[3][0] + results[4][0]/2
#    results[1][1], results[1][2] = results[1][2], results[1][1] #swap uncertainties of e


#write results to console
#print('Results:')
#for i in range(6):
#    print(results[i][0], '+',results[i][1], '-',results[i][2])



print('RMS error: ', round(residuals([results[0][0], results[1][0], results[2][0],
                                results[3][0], results[4][0], results[5][0]], mass_ratio, RVp, RVs, JDp, JDs), 3))


#write results to log file
table = open('log.txt', 'a+')
labels = ('K', 'e', 'w', 'T', 'P', 'y')
print('\n' , system, " Results:", file = table)
print('RMS error: ', residuals(np.transpose(results)[0], mass_ratio, RVp, RVs, JDp, JDs), file = table)
print('q  = ', mass_ratio, ' +/-  ', standard_error , file = table)
for i in range(6):
    print(labels[i], ' = ', results[i][0], ' +', results[i][1], ' -', results[i][2], file = table)
table.close()

#end timer
end = time.time()
elapsed = end-start
print('Fitting time was ', int(elapsed), ' seconds.')

#create the curves plot
x = np.linspace(0, np.transpose(results)[0][4], num=1000)
fig, ax = plt.figure(figsize=(15,8)), plt.subplot(111)
primary, secondary = RV(x, mass_ratio, [results[0][0], results[1][0], results[2][0],
                                        results[3][0], results[4][0], results[5][0]])
ax.plot(x/results[4][0], primary, 'b', lw=2)
ax.plot(x/results[4][0], secondary, 'r', lw=2)
ax.plot(x, np.ones(len(x))*results[5][0], 'k' , label='Systemic Velocity')
ax.plot(phases(results[4][0], JDp), RVp, 'bs', label='Primary RV Data') #data phased to result period
ax.plot(phases(results[4][0], JDs), RVs, 'rs', label='Secondary RV data')
ax.set_xlim([0,1])
plt.xlabel('Orbital Phase', fontsize = 18)
plt.ylabel('Radial Velocity $\\frac{km}{s}$', fontsize = 18)
plt.title('Radial Velocity Curve', fontsize = 18)
#plt.title(residuals([results[0][0], results[1][0], results[2][0],
#                     results[3][0], results[4][0], results[5][0]], mass_ratio, RVp, RVs, JDp, JDs))
plt.savefig(file + ' curve_results.png')
#plt.show()

#create the corner plot
corner(6, samples, lower_bounds, upper_bounds, np.transpose(results)[0]).savefig(file + ' %s dimension walk results.png'%(6))

del samples

'''
#-------------circular---MCMC---------------#

start = time.time() #start timer

#take a walk
sampler = MCMC(mass_ratio, gamma, RVp, RVs, JDp, JDs, lower_bounds, upper_bounds, 4, nwalkers, nsteps, 4)

#save the results of the walk
circular_samples = sampler.chain[:, cutoff:, :].reshape((-1, 4))

results = np.asarray(list(map(lambda v: (v[1], v[2]-v[1], v[1]-v[0]),
                              zip(*np.percentile(circular_samples, [16, 50, 84], axis=0)))))

results = np.transpose(results)
results[0] = kernelDensityP(circular_samples)
results = np.transpose(results)


#write results to console
#print('Results:')
#for i in range(4):
#    print(results[i][0], '+',results[i][1], '-',results[i][2])

print('RMS error: ', round(residuals([results[0][0], results[1][0],
                                results[2][0], results[3][0]], mass_ratio, RVp, RVs, JDp, JDs), 3))


#write results to log file
table = open('log.txt', 'a+')
labels = ('K', 'T', 'P', 'y')
print('\n' , system, " Results:", file = table)
print('RMS error: ', residuals([results[0][0], results[1][0], results[2][0],
                                results[3][0]], mass_ratio, RVp, RVs, JDp, JDs), file = table)
print('q  = ', mass_ratio, ' +/-  ', standard_error , file = table)
for i in range(4):
    print(labels[i], ' = ', results[i][0], ' +', results[i][1], ' -', results[i][2], file = table)
table.close()

#end timer
end = time.time()
elapsed = end-start
print('Fitting time was ', int(elapsed), ' seconds.')

#create the curves plot
x = np.linspace(0, results[2][0], num=1000)
fig, ax = plt.figure(figsize=(15,8)), plt.subplot(111)
primary, secondary = RV(x, mass_ratio, [results[0][0], results[1][0], results[2][0], results[3][0]])
ax.plot(x/results[2][0], primary, 'b', lw=2)
ax.plot(x/results[2][0], secondary, 'r', lw=2)
ax.plot(x, np.ones(len(x))*results[3][0], 'k' , label='Systemic Velocity')
ax.plot(phases(results[2][0], JDp), RVp, 'bs', label='Primary RV Data') #data phased to result period
ax.plot(phases(results[2][0], JDs), RVs, 'rs', label='Secondary RV data')
ax.set_xlim([0,1])
plt.xlabel('Orbital Phase', fontsize = 18)
plt.ylabel('Radial Velocity $\\frac{km}{s}$', fontsize = 18)
plt.title('Radial Velocity Curve', fontsize = 18)
#plt.title(residuals([results[0][0], results[1][0],
#                     results[2][0], results[3][0]], mass_ratio, RVp, RVs, JDp, JDs))
plt.savefig(file + ' no e curve_results.png')

#create the corner plot
corner(file, 4, circular_samples, lower_bounds, upper_bounds, np.transpose(results)[0])

#create the walkers plot
walkers(file, nsteps, 4, sampler, results)
#plt.show()
'''