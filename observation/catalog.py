"""
Classes which manage object catalogs live here.
"""

import numpy
import pyfits
import healpy
import copy

import ugali.utils.projector
import ugali.utils.config

from ugali.utils.projector import gal2cel,cel2gal
from ugali.utils.healpix import ang2pix,superpixel
from ugali.utils.logger import logger
############################################################

class Catalog:

    def __init__(self, config, roi=None, data=None):
        """
        Class to store information about detected objects.

        The raw data from the fits file is stored. lon and lat are derived quantities
        based on chosen coordinate system.

        INPUTS:
            config: Config object
            roi[None] : Region of Interest to load catalog data for
            data[None]: pyfits table data (fitsrec) object.
        """
        #self = config.merge(config_merge) # Maybe you would want to update parameters??
        self.config = config

        if data is None:
            self._parse(roi)
        else:
            self.data = data
    
        self._defineVariables()

    def applyCut(self, cut):
        """
        Return a new catalog which is a subset of objects selected using the input cut array.
        """
        return Catalog(self.config, data=self.data[cut])

    def bootstrap(self, mc_bit=0x10, seed=None):
        """
        Return a random catalog by boostrapping the colors of the objects in the current catalog.
        """
        if seed is not None: numpy.random.seed(seed)
        data = copy.deepcopy(self.data)
        idx = numpy.random.randint(0,len(data),len(data))
        data[self.config['catalog']['mag_1_field']][:] = self.mag_1[idx]
        data[self.config['catalog']['mag_err_1_field']][:] = self.mag_err_1[idx]
        data[self.config['catalog']['mag_2_field']][:] = self.mag_2[idx]
        data[self.config['catalog']['mag_err_2_field']][:] = self.mag_err_2[idx]
        data[self.config['catalog']['mc_source_id_field']][:] |= mc_bit
        return Catalog(self.config, data=data)

    def project(self, projector = None):
        """
        Project coordinates on sphere to image plane using Projector class.
        """
        if projector is None:
            try:
                self.projector = ugali.utils.projector.Projector(self.config['coords']['reference'][0],
                                                                 self.config['coords']['reference'][1])
            except KeyError:
                logger.warning('Projection reference point is median (lon, lat) of catalog objects')
                self.projector = ugali.utils.projector.Projector(numpy.median(self.lon), numpy.median(self.lat))
        else:
            self.projector = projector

        self.x, self.y = self.projector.sphereToImage(self.lon, self.lat)

    def spatialBin(self, roi):
        """
        Return indices of ROI pixels corresponding to object locations.
        """
        # ADW: Not safe to set index = -1 (since it will access last entry); 
        # np.inf would be better...
        self.pixel = ang2pix(self.config['coords']['nside_pixel'],self.lon,self.lat)
        self.pixel_roi_index = roi.indexROI(self.lon,self.lat)

        if numpy.any(self.pixel_roi_index < 0):
            logger.warning("Objects found outside ROI")

    def write(self, outfile):
        """
        Write the current object catalog to fits file.
        """
            
        hdu = pyfits.BinTableHDU(self.data)
        hdu.writeto(outfile, clobber=True)

    def plotCMD(self, mode='scatter'):
        """
        Show the color-magnitude diagram for catalog objects as scatter plot or two-dimensional histogram.
        """
        import pylab
        import ugali.utils.plotting

        if mode == 'scatter':
            ugali.utils.plotting.twoDimensionalScatter('test', 'color (mag)', 'mag (mag)',
                                                       self.color, self.mag)
            y_min, y_max = pylab.axis()[2], pylab.axis()[3]
            pylab.ylim(y_max, y_min)
        elif mode == 'histogram':
            # ROI object needed here
            pass
        else:
            logger.warning('Unrecognized plotting mode %s'%(mode))

    def plotMap(self, mode='scatter'):
        """
        Show map of catalog objects in image (projected) coordinates.
        """
        import ugali.utils.plotting

        if mode == 'scatter':
            ugali.utils.plotting.twoDimensionalScatter('test', r'$\Delta$x', '$\Delta$y',
                                                       self.x, self.y, color=self.color)
                                                       #lim_x = lim_x
                                                       #lim_y = lim_y)
        else:
            logger.warning('Unrecognized plotting mode %s'%(mode))

    def plotMag(self):
        """

        """
        pass

    def _parse(self, roi=None):
        """
        Helper function to parse a catalog file and return a pyfits table.

        CSV format not yet validated.

        !!! Careful, reading a large catalog is memory intensive !!!
        """
        
        filenames = self.config.getFilenames()

        if len(filenames['catalog'].compressed()) == 0:
            raise Exception("No catalog file found")
        elif roi is not None:
            pixels = roi.getCatalogPixels()
            self.data = readCatalogData(filenames['catalog'][pixels])
        elif len(filenames['catalog'].compressed()) == 1:
            file_type = filenames[0].split('.')[-1].strip().lower()
            if file_type == 'csv':
                self.data = numpy.recfromcsv(filenames[0], delimiter = ',')
            elif file_type in ['fit', 'fits']:
                self.data = pyfits.open(filenames[0])[1].data
            else:
                logger.warning('Unrecognized catalog file extension %s'%(file_type))
        else:
            self.data = readCatalogData(filenames['catalog'].compressed())
        #print 'Found %i objects'%(len(self.data))

    def _defineVariables(self):
        """
        Helper funtion to define pertinent variables from catalog data.
        """
        self.objid = self.data.field(self.config['catalog']['objid_field'])
        self.lon = self.data.field(self.config['catalog']['lon_field'])
        self.lat = self.data.field(self.config['catalog']['lat_field'])

        if self.config['catalog']['coordsys'].lower() == 'cel' \
           and self.config['coords']['coordsys'].lower() == 'gal':
            logger.info('Converting catalog objects from CELESTIAL to GALACTIC cboordinates')
            self.lon, self.lat = ugali.utils.projector.celToGal(self.lon, self.lat)
        elif self.config['catalog']['coordsys'].lower() == 'gal' \
           and self.config['coords']['coordsys'].lower() == 'cel':
            logger.info('Converting catalog objects from GALACTIC to CELESTIAL coordinates')
            self.lon, self.lat = ugali.utils.projector.galToCel(self.lon, self.lat)

        self.mag_1 = self.data.field(self.config['catalog']['mag_1_field'])
        self.mag_err_1 = self.data.field(self.config['catalog']['mag_err_1_field'])
        self.mag_2 = self.data.field(self.config['catalog']['mag_2_field'])
        self.mag_err_2 = self.data.field(self.config['catalog']['mag_err_2_field'])

        if self.config['catalog']['mc_source_id_field'] is not None:
            if self.config['catalog']['mc_source_id_field'] in self.data.names:
                self.mc_source_id = self.data.field(self.config['catalog']['mc_source_id_field'])
                logger.info('Found %i MC source objects'%(numpy.sum(self.mc_source_id > 0)))
            else:
                columns_array = [pyfits.Column(name = self.config['catalog']['mc_source_id_field'],
                                               format = 'I',
                                               array = numpy.zeros(len(self.data)))]
                hdu = pyfits.new_table(columns_array)
                self.data = pyfits.new_table(pyfits.new_table(self.data).columns + hdu.columns).data
                self.mc_source_id = self.data.field(self.config['catalog']['mc_source_id_field'])

        if self.config['catalog']['band_1_detection']:
            self.mag = self.mag_1
            self.mag_err = self.mag_err_1
        else:
            self.mag = self.mag_2
            self.mag_err = self.mag_err_2
            
        self.color = self.mag_1 - self.mag_2
        self.color_err = numpy.sqrt(self.mag_err_1**2 + self.mag_err_2**2)

        logger.info('Catalog contains %i objects'%(len(self.data)))

############################################################

def mergeCatalogs(catalog_array):
    """
    Input is an array of Catalog objects. Output is a merged catalog object.
    Column names are derived from first Catalog in the input array.
    """
    len_array = []
    for ii in range(0, len(catalog_array)):
        len_array.append(len(catalog_array[ii].data))
    cumulative_len_array = numpy.cumsum(len_array)
    cumulative_len_array = numpy.insert(cumulative_len_array, 0, 0)

    columns = pyfits.new_table(catalog_array[0].data).columns
    hdu = pyfits.new_table(columns, nrows=cumulative_len_array[-1])
    for name in columns.names:
        for ii in range(0, len(catalog_array)):
            if name not in catalog_array[ii].data.names:
                continue
            hdu.data.field(name)[cumulative_len_array[ii]: cumulative_len_array[ii + 1]] = catalog_array[ii].data.field(name)

    catalog_merged = Catalog(catalog_array[0].config, data=hdu.data)
    return catalog_merged


############################################################

def precomputeCoordinates(infile, outfile):
    import numpy.lib.recfunctions as rec
    hdu = pyfits.open(infile)
    data = hdu[1].data
    columns = hdu[1].columns
    names = [n.lower() for n in hdu[1].data.names]

    if 'glon' not in names and 'glat' not in names:
        logger.info("Writing 'GLON' and 'GLAT' columns")
        glon, glat = ugali.utils.projector.celToGal(data['ra'], data['dec'])
        out = rec.append_fields(data,['GLON','GLAT'],[glon,glat],
                                usemask=False,asrecarray=True)
    elif 'ra' not in names and 'dec' not in names:
        logger.info("Writing 'RA' and 'DEC' columns")
        ra, dec = ugali.utils.projector.galToCel(data['glat'], data['glon'])
        out = rec.append_fields(data,['RA','DEC'],[ra,dec],
                                usemask=False,asrecarray=True)
    
    hdu_out = pyfits.BinTableHDU(out)
    hdu_out.writeto(outfile, clobber=True)

############################################################

def readCatalogData(infiles):
    """ Read a set of catalog FITS files into a single recarray. """
    if isinstance(infiles,basestring): infiles = [infiles]
    data, len_data = [],[]
    for f in infiles:
        data.append(pyfits.open(f)[1].data)
        len_data.append(len(data[-1]))

    cumulative_len_array = numpy.cumsum(len_data)
    cumulative_len_array = numpy.insert(cumulative_len_array, 0, 0)
    columns = data[0].columns
    table = pyfits.new_table(columns, nrows=cumulative_len_array[-1])

    for name in columns.names:
        for ii in range(0, len(data)):
            if name not in data[ii].names:
                raise Exception("Column %s not found in %"(name,infiles[ii]))
            table.data.field(name)[cumulative_len_array[ii]: cumulative_len_array[ii + 1]] = data[ii].field(name)
    return table.data
