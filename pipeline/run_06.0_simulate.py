#!/usr/bin/env python
import glob
import os
from os.path import join, exists, basename, splitext
import time

import numpy as np
import numpy.lib.recfunctions as recfuncs
import pyfits

from ugali.analysis.pipeline import Pipeline
import ugali.analysis.loglike
import ugali.simulation.simulator
import ugali.utils.plotting
import ugali.utils.skymap

from ugali.utils.shell import mkdir
from ugali.utils.logger import logger
from ugali.utils.healpix import pix2ang


description="Simulate the likelihood search."
components = ['simulate','merge','plot']

def run(self):
    outdir=self.config['output']['simdir']
    logdir=join(outdir,'log')

    if 'simulate' in self.opts.run:
        logger.info("Running 'simulate'...")
        mkdir(outdir)
        mkdir(logdir)

        for i in range(self.config['simulate']['njobs']):
            outfile=join(outdir,self.config['output']['simfile']%i)
            base = splitext(basename(outfile))[0]
            logfile=join(logdir,base+'.log')
            jobname=base
            script = self.config['simulate']['script']
            cmd='%s %s %s --seed %i'%(script,self.opts.config,outfile,i)
            #cmd='%s %s %s'%(script,self.opts.config,outfile)
            self.batch.submit(cmd,jobname,logfile)
            time.sleep(0.1)

    if 'sensitivity' in self.opts.run:
        logger.info("Running 'sensitivity'...")

    if 'merge' in self.opts.run:
        logger.info("Running 'merge'...")
        filenames=join(outdir,self.config['output']['simfile']).split('_%')[0]+'_*'
        infiles=sorted(glob.glob(filenames))

        f = pyfits.open(infiles[0])
        table = np.empty(0,dtype=f[1].data.dtype)
        for filename in infiles:
            logger.debug("Reading %s..."%filename)
            f = pyfits.open(filename)
            t = f[1].data[~np.isnan(f[1].data['ts'])]
            table = recfuncs.stack_arrays([table,t],usemask=False,asrecarray=True)

        logger.info("Found %i simulations."%len(table))
        outfile = join(outdir,"merged_sims.fits")
        hdu = pyfits.new_table(table)
        logger.info("Writing %s..."%outfile)
        hdu.writeto(outfile,clobber=True)

    if 'plot' in self.opts.run:
        logger.info("Running 'plot'...")
        import pylab as plt
        import scipy.stats

        data = pyfits.open(join(outdir,"merged_sims.fits"))[1].data
        data = data[~np.isnan(data['ts'])]
        ugali.utils.plotting.plotChernoff(data['ts'])
        #idx=np.random.randint(len(data['ts'])-1,size=400)
        #idx=slice(400)
        #ugali.utils.plotting.plotChernoff(data['ts'][idx])
        #ugali.utils.plotting.plotChernoff(data['fit_ts'])

        """
        try:
            fig = plt.figure()
            x = range(len(data))
            y = data['fit_mass']/data['stellar_mass']
            yclip,lo,hi = scipy.stats.sigmaclip(y)
            yerr = data['fit_mass_err']/data['stellar_mass']
             
            plt.errorbar(x,y,yerr=yerr,fmt='o',c='k')
            plt.axhline(1,ls='--',c='gray',lw=2)
            plt.axhline(np.mean(yclip),ls='--',c='r',lw=2)
            plt.ylim(lo,hi)
            plt.ylabel("Best-Fit Mass Residual")
            plt.xlabel("Simulation Number")
        except:
            pass
        """

Pipeline.run = run
pipeline = Pipeline(description,components)
pipeline.parser.add_argument('-n','--num',default=100,type=int)
pipeline.parse_args()
pipeline.execute()

import pylab as plt
