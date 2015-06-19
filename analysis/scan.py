#!/usr/bin/env python
"""
Class to create and run an individual likelihood analysis.

Classes:
    Scan -- ADW: Doesn't do anything
    GridSearch -- ADW: Should be renamed to Scan

"""

import os
import sys
from collections import OrderedDict as odict

import numpy
import numpy as np
import pyfits
import healpy

import ugali.utils.skymap
from ugali.analysis.loglike  import LogLikelihood 

from ugali.utils.parabola import Parabola

from ugali.utils.config import Config
from ugali.utils.logger import logger
from ugali.utils.healpix import superpixel, subpixel, pix2ang, ang2pix

############################################################

class Scan(object):
    """
    The base of a likelihood analysis scan.

    ADW: This really does nothing now...
    """
    def __init__(self, config, coords):
        self.config = Config(config)
        # Should only be one coordinate
        if len(coords)!=1: raise Exception('Must specify one coordinate.')
        self.lon,self.lat,radius = coords[0]
        self._setup()

    def _setup(self):
        #self.nside_catalog    = self.config['coords']['nside_catalog']
        #self.nside_likelihood = self.config['coords']['nside_likelihood']
        #self.nside_pixel      = self.config['coords']['nside_pixel']

        # All possible filenames
        #self.filenames = self.config.getFilenames()
        # ADW: Might consider storing only the good filenames
        # self.filenames = self.filenames.compress(~self.filenames.mask['pix'])

        #self.roi = ugali.observation.roi.ROI(self.config, self.lon, self.lat)
        self.roi = self.createROI(self.config,self.lon,self.lat)
        ### # All possible catalog pixels spanned by the ROI
        ### catalog_pixels = numpy.unique(superpixel(self.roi.pixels,self.nside_pixel,self.nside_catalog))
        ### # Only catalog pixels that exist in catalog files
        ### self.catalog_pixels = numpy.intersect1d(catalog_pixels, self.filenames['pix'].compressed())

        self.kernel = self.createKernel(self.config,self.lon,self.lat)
        self.isochrone = self.createIsochrone(self.config)
        self.catalog = self.createCatalog(self.config,self.roi)
        self.mask = self.createMask(self.config,self.roi)

        self.grid = GridSearch(self.config, self.roi, self.mask,self.catalog, 
                               self.isochrone, self.kernel)

    @property
    def loglike(self):
        return self.grid.loglike

    @staticmethod
    def createROI(config,lon,lat):
        return ugali.analysis.loglike.createROI(config,lon,lat)

    @staticmethod
    def createKernel(config,lon=0.0,lat=0.0):
        # ADW: This is sort of a hack
        if config['scan'].get('kernel') is not None:
            return ugali.analysis.loglike.createKernel(config['scan'],lon,lat)
        else:
            return ugali.analysis.loglike.createKernel(config,lon,lat)

    @staticmethod
    def createIsochrone(config):
        # ADW: This is sort of a hack
        if config['scan'].get('isochrone') is not None:
            config = dict(config)
            config.update(isochrone=config['scan']['isochrone'])
            return ugali.analysis.loglike.createIsochrone(config)
        else:
            return ugali.analysis.loglike.createIsochrone(config)

    @staticmethod
    def createCatalog(config,roi=None,lon=None,lat=None):
        return ugali.analysis.loglike.createCatalog(config,roi,lon,lat)

    @staticmethod
    def simulateCatalog(config,roi=None,lon=None,lat=None):
        return ugali.analysis.loglike.simulateCatalog(config,roi,lon,lat)

    @staticmethod
    def createMask(config,roi=None,lon=None,lat=None):
        return ugali.analysis.loglike.createMask(config,roi,lon,lat)

    @staticmethod
    def createLoglike(config,lon=None,lat=None):
        return ugali.analysis.loglike.createLoglike(config,roi,lon,lat)

    def run(self, coords=None, debug=False):
        """
        Run the likelihood grid search
        """
        #self.grid.precompute()
        self.grid.search(coords=coords)
        return self.grid
        
    def write(self, outfile):
        self.grid.write(outfile)


############################################################

class GridSearch:

    def __init__(self, config, roi, mask, catalog, isochrone, kernel):
        """
        Object to efficiently search over a grid of ROI positions.
        """

        self.config = config
        self.roi  = roi
        self.mask = mask # Currently assuming that input mask is ROI-specific

        logger.info("Creating log-likelihood...")
        self.loglike=LogLikelihood(config,roi,mask,catalog,isochrone,kernel)
        logger.info(str(self.loglike))
        self.stellar_mass_conversion = self.loglike.stellar_mass()
        self.distance_modulus_array = np.asarray(self.config['scan']['distance_modulus_array'])

    def precompute(self, distance_modulus_array=None):
        """
        Precompute u_background and u_color for each star in catalog.
        Precompute observable fraction in each ROI pixel.
        # Precompute still operates over the full ROI, not just the likelihood region
        """
        if distance_modulus_array is not None:
            self.distance_modulus_array = distance_modulus_array
        else:
            self.distance_modulus_array = sel

        # Observable fraction for each pixel
        self.u_color_array = [[]] * len(self.distance_modulus_array)
        self.observable_fraction_sparse_array = [[]] * len(self.distance_modulus_array)

        logger.info('Looping over distance moduli in precompute ...')
        for ii, distance_modulus in enumerate(self.distance_modulus_array):
            logger.info('  (%i/%i) Distance Modulus = %.2f ...'%(ii+1, len(self.distance_modulus_array), distance_modulus))

            self.u_color_array[ii] = False
            if self.config['scan']['color_lut_infile'] is not None:
                logger.info('  Precomputing signal color from %s'%(self.config['scan']['color_lut_infile']))
                self.u_color_array[ii] = ugali.analysis.color_lut.readColorLUT(self.config['scan']['color_lut_infile'],
                                                                               distance_modulus,
                                                                               self.loglike.catalog.mag_1,
                                                                               self.loglike.catalog.mag_2,
                                                                               self.loglike.catalog.mag_err_1,
                                                                               self.loglike.catalog.mag_err_2)
            if not numpy.any(self.u_color_array[ii]):
                logger.info('  Precomputing signal color on the fly...')
                self.u_color_array[ii] = self.loglike.calc_signal_color(distance_modulus) 
            
            # Calculate over all pixels in ROI
            self.observable_fraction_sparse_array[ii] = self.loglike.calc_observable_fraction(distance_modulus)
            
        self.u_color_array = numpy.array(self.u_color_array)

                
    def search(self, coords=None, distance_modulus=None, tolerance=1.e-2):
        """
        Organize a grid search over ROI target pixels and distance moduli in distance_modulus_array
        coords: (lon,lat)
        distance_modulus: scalar
        """
        nmoduli = len(self.distance_modulus_array)
        npixels    = len(self.roi.pixels_target)
        self.log_likelihood_sparse_array       = numpy.zeros([nmoduli, npixels])
        self.richness_sparse_array             = numpy.zeros([nmoduli, npixels])
        self.richness_lower_sparse_array       = numpy.zeros([nmoduli, npixels])
        self.richness_upper_sparse_array       = numpy.zeros([nmoduli, npixels])
        self.richness_upper_limit_sparse_array = numpy.zeros([nmoduli, npixels])
        self.stellar_mass_sparse_array         = numpy.zeros([nmoduli, npixels])
        self.fraction_observable_sparse_array  = numpy.zeros([nmoduli, npixels])

        # Specific pixel/distance_modulus
        coord_idx, distance_modulus_idx = None, None
        if coords is not None:
            # Match to nearest grid coordinate index
            coord_idx = self.roi.indexTarget(coords[0],coords[1])
        if distance_modulus is not None:
            # Match to nearest distance modulus index
            distance_modulus_idx=np.fabs(self.distance_modulus_array-distance_modulus).argmin()

        lon, lat = self.roi.pixels_target.lon, self.roi.pixels_target.lat
            
        logger.info('Looping over distance moduli in grid search ...')
        for ii, distance_modulus in enumerate(self.distance_modulus_array):

            # Specific pixel
            if distance_modulus_idx is not None:
                if ii != distance_modulus_idx: continue

            logger.info('  (%-2i/%i) Distance Modulus=%.1f ...'%(ii+1,nmoduli,distance_modulus))

            # Set distance_modulus once to save time
            self.loglike.set_params(distance_modulus=distance_modulus)

            for jj in range(0, npixels):
                # Specific pixel
                if coord_idx is not None:
                    if jj != coord_idx: continue

                # Set kernel location
                self.loglike.set_params(lon=lon[jj],lat=lat[jj])
                # Doesn't re-sync distance_modulus each time
                self.loglike.sync_params()
                                         
                args = (jj+1, npixels, self.loglike.lon, self.loglike.lat)
                message = '    (%-3i/%i) Candidate at (%.2f, %.2f) ... '%(args)

                self.log_likelihood_sparse_array[ii][jj], self.richness_sparse_array[ii][jj], parabola = self.loglike.fit_richness()
                self.stellar_mass_sparse_array[ii][jj] = self.stellar_mass_conversion * self.richness_sparse_array[ii][jj]
                self.fraction_observable_sparse_array[ii][jj] = self.loglike.f
                if self.config['scan']['full_pdf']:
                    #n_pdf_points = 100
                    #richness_range = parabola.profileUpperLimit(delta=25.) - self.richness_sparse_array[ii][jj]
                    #richness = numpy.linspace(max(0., self.richness_sparse_array[ii][jj] - richness_range),
                    #                          self.richness_sparse_array[ii][jj] + richness_range,
                    #                          n_pdf_points)
                    #if richness[0] > 0.:
                    #    richness = numpy.insert(richness, 0, 0.)
                    #    n_pdf_points += 1
                    # 
                    #log_likelihood = numpy.zeros(n_pdf_points)
                    #for kk in range(0, n_pdf_points):
                    #    log_likelihood[kk] = self.loglike.value(richness=richness[kk])
                    #parabola = ugali.utils.parabola.Parabola(richness, 2.*log_likelihood)
                    #self.richness_lower_sparse_array[ii][jj], self.richness_upper_sparse_array[ii][jj] = parabola.confidenceInterval(0.6827)
                    self.richness_lower_sparse_array[ii][jj], self.richness_upper_sparse_array[ii][jj] = self.loglike.richness_interval(0.6827)
                    
                    self.richness_upper_limit_sparse_array[ii][jj] = parabola.bayesianUpperLimit(0.95)

                    args = (
                        2. * self.log_likelihood_sparse_array[ii][jj],
                        self.stellar_mass_conversion*self.richness_sparse_array[ii][jj],
                        self.stellar_mass_conversion*self.richness_lower_sparse_array[ii][jj],
                        self.stellar_mass_conversion*self.richness_upper_sparse_array[ii][jj],
                        self.stellar_mass_conversion*self.richness_upper_limit_sparse_array[ii][jj]
                    )
                    message += 'TS=%.1f, Stellar Mass=%.1f (%.1f -- %.1f @ 0.68 CL, < %.1f @ 0.95 CL)'%(args)
                else:
                    args = (
                        2. * self.log_likelihood_sparse_array[ii][jj], 
                        self.stellar_mass_conversion * self.richness_sparse_array[ii][jj],
                        self.fraction_observable_sparse_array[ii][jj]
                    )
                    message += 'TS=%.1f, Stellar Mass=%.1f, Fraction=%.2g'%(args)
                logger.debug( message )
                
                #if coords is not None and distance_modulus is not None:
                #    results = [self.richness_sparse_array[ii][jj],
                #               self.log_likelihood_sparse_array[ii][jj],
                #               self.richness_lower_sparse_array[ii][jj],
                #               self.richness_upper_sparse_array[ii][jj],
                #               self.richness_upper_limit_sparse_array[ii][jj],
                #               richness, log_likelihood, self.loglike.p, self.loglike.f]
                #    return results

            jj_max = self.log_likelihood_sparse_array[ii].argmax()
            args = (
                jj_max+1, npixels, lon[jj_max], lat[jj_max],
                2. * self.log_likelihood_sparse_array[ii][jj_max], 
                self.stellar_mass_conversion * self.richness_sparse_array[ii][jj_max]
            )
            message = '  (%-3i/%i) Maximum at (%.2f, %.2f) ... TS=%.1f, Stellar Mass=%.1f'%(args)
            logger.info( message )
 
    def mle(self):
        a = self.log_likelihood_sparse_array
        j,k = np.unravel_index(a.argmax(),a.shape)
        mle = odict()
        mle['richness'] = self.richness_sparse_array[j][k]
        mle['lon'] = self.roi.pixels_target.lon[k]
        mle['lat'] = self.roi.pixels_target.lat[k]
        mle['distance_modulus'] = self.distance_modulus_array[j]
        mle['extension'] = float(self.loglike.extension)
        mle['ellipticity'] = float(self.loglike.ellipticity)
        mle['position_angle'] = float(self.loglike.position_angle)
        # ADW: FIXME!
        try: 
            mle['age'] = np.mean(self.loglike.age)
            mle['metallicity'] = np.mean(self.loglike.metallicity)
        except AttributeError:
            mle['age'] = np.nan
            mle['metallicity'] = np.nan
            
        return mle

    def err(self):
        """
        A few rough approximations of the fit uncertainty. These
        values shouldn't be trusted for anything real (use MCMC instead).
        """
        # Initiallize error to nan
        err = odict(self.mle())
        err.update([(k,np.nan*np.ones(2)) for k in err.keys()])

        # Find the maximum likelihood
        a = self.log_likelihood_sparse_array
        j,k = np.unravel_index(a.argmax(),a.shape)

        self.loglike.set_params(distance_modulus=self.distance_modulus_array[j],
                                lon=self.roi.pixels_target.lon[k],
                                lat=self.roi.pixels_target.lat[k])
        self.loglike.sync_params()

        # Find the error in richness, starting at maximum
        lo,hi = np.array(self.loglike.richness_interval())
        err['richness'] = np.array([lo,hi])

        # ADW: This is a rough estimate of the distance uncertainty 
        # hacked to keep the maximum distance modulus on a grid index

        # This is a hack to get the confidence interval to play nice...
        # Require at least three points.
        if (a[:,k]>0).sum() >= 3:
            parabola = Parabola(np.insert(self.distance_modulus_array,0,0.), 
                                np.insert(a[:,k],0,0.) )
            lo,hi = np.array(parabola.confidenceInterval())
            err['distance_modulus'] = self.distance_modulus_array[j] + (hi-lo)/2.*np.array([-1.,1.])

        # ADW: Could estimate lon and lat from the grid.
        # This is just concept right now...
        if (a[j,:]>0).sum() >= 10:
            delta_ts = 2*(a[j,k] - a[j,:])
            pix = np.where(a[j,:][delta_ts < 2.71])[0]
            lons = self.roi.pixels_target.lon[pix]
            lats = self.roi.pixels_target.lat[pix]
            err['lon'] = np.array([ np.min(lons),np.max(lons)])
            err['lat'] = np.array([ np.min(lats),np.max(lats)])

        return err

    def write(self, outfile):
        """
        Save the likelihood fitting results as a sparse HEALPix map.
        """
        # Full data output (too large for survey)
        if self.config['scan']['full_pdf']:
            data_dict = {'LOG_LIKELIHOOD': self.log_likelihood_sparse_array.transpose(),
                         'RICHNESS':       self.richness_sparse_array.transpose(),
                         'RICHNESS_LOWER': self.richness_lower_sparse_array.transpose(),
                         'RICHNESS_UPPER': self.richness_upper_sparse_array.transpose(),
                         'RICHNESS_LIMIT': self.richness_upper_limit_sparse_array.transpose(),
                         #'STELLAR_MASS': self.stellar_mass_sparse_array.transpose(),
                         'FRACTION_OBSERVABLE': self.fraction_observable_sparse_array.transpose()}
        else:
            data_dict = {'LOG_LIKELIHOOD': self.log_likelihood_sparse_array.transpose(),
                         'RICHNESS': self.richness_sparse_array.transpose(),
                         'FRACTION_OBSERVABLE': self.fraction_observable_sparse_array.transpose()}

        # Stellar Mass can be calculated from STELLAR * RICHNESS
        header_dict = {
            'STELLAR' : round(self.stellar_mass_conversion,8),
            'LKDNSIDE': self.config['coords']['nside_likelihood'],
            'LKDPIX'  : ang2pix(self.config['coords']['nside_likelihood'],self.roi.lon,self.roi.lat),
            'NROI'    : self.roi.inROI(self.loglike.catalog_roi.lon,self.loglike.catalog_roi.lat).sum(), 
            'NANNULUS': self.roi.inAnnulus(self.loglike.catalog_roi.lon,self.loglike.catalog_roi.lat).sum(), 
            'NINSIDE' : self.roi.inInterior(self.loglike.catalog_roi.lon,self.loglike.catalog_roi.lat).sum(), 
            'NTARGET' : self.roi.inTarget(self.loglike.catalog_roi.lon,self.loglike.catalog_roi.lat).sum(), 
        }

        # In case there is only a single distance modulus
        if len(self.distance_modulus_array) == 1:
            for key in data_dict:
                data_dict[key] = data_dict[key].flatten()

        ugali.utils.skymap.writeSparseHealpixMap(self.roi.pixels_target,
                                                 data_dict,
                                                 self.config['coords']['nside_pixel'],
                                                 outfile,
                                                 distance_modulus_array=self.distance_modulus_array,
                                                 coordsys='NULL', ordering='NULL',
                                                 header_dict=header_dict)

############################################################
    
if __name__ == "__main__":
    import ugali.utils.parser
    description = "Script for executing the likelihood scan."
    parser = ugali.utils.parser.Parser(description=description)
    parser.add_config()
    parser.add_argument('outfile',metavar='outfile.fits',help='Output fits file.')
    parser.add_debug()
    parser.add_verbose()
    parser.add_coords(required=True,radius=False)
    opts = parser.parse_args()

    #print opts.coords
    scan = Scan(opts.config,opts.coords)
    if not opts.debug:
        result = scan.run()
        scan.write(opts.outfile)
