#!/usr/bin/env python

import numpy
import numpy as np
import sys
import subprocess
import re
import os
import httplib
import StringIO

from ugali.utils.logger import logger
import ugali.utils.shell

DATABASES = {
    'sdss':['dr10'],
    'des' :['sva1'],
    }

def databaseFactory(config):
    if config.params['data']['survey'].lower() == 'sdss':
        return SDSSDatabase(release = config.params['data']['survey'])
    elif config.params['data']['survey'].lower() == 'des':
        return DESDatabase(release = config.params['data']['survey'])
    else:
        logger.error("Unrecognized survey %s"%config.params['data']['survey'])
        return None

class Database(object):
    def __init__(self):
        pass

    def load_pixels(self, pixfile=None):
        if pixfile is not None:
            self.pixels = np.loadtxt(pixfile,dtype=[('name',int),('ra_min',float),('ra_max',float),
                                                    ('dec_min',float),('dec_max',float)])
            # One-line input file
            if self.pixels.ndim == 0: self.pixels = np.array([self.pixels])
        else:
            ra_step = 20
            ra_range = np.around(np.arange(0,360+ra_step,ra_step),0)
            sin_dec_step = -0.2
            # Decreasing dec...
            dec_range = np.around(np.degrees(np.arcsin(np.arange(1,-1+sin_dec_step,sin_dec_step))),0)
            xx, yy = np.meshgrid( ra_range,dec_range)
            ra_min  = xx[1:,:-1].flatten(); ra_max = xx[1:,1:].flatten()
            dec_min = yy[1:,1:].flatten(); dec_max = yy[:-1,1:].flatten() # Decreasing...
            name = np.arange(len(ra_min),dtype=int)
            self.pixels = np.rec.fromarrays([name, ra_min, ra_max, dec_min, dec_max],
                                            dtype=[('name',int),('ra_min',float),('ra_max',float),
                                                   ('dec_min',float),('dec_max',float)])

    def generate_query(self):
        """ Should be implemented by child class. """
        pass

    def download(self):
        """ Should be implemented by child class. """        
        pass

    def run(self):
        """ Should be implemented by child class. """
        pass

class SDSSDatabase(Database):
    """
    For downloading SDSS DR10 data set.
    """
    def __init__(self,release='DR10'):
        super(SDSSDatabase,self).__init__()
        self.release = release.lower()
        self.basename = "sdss_%s_photometry"%self.release

    def _setup_casjobs(self):
        # Function here to install casjobs.jar and CasJobs.config
        pass

    def generate_query(self, ra_min,ra_max,dec_min,dec_max,filename,db):
        outfile = open(filename,"w")
        outfile.write('SELECT s.objID, s.ra AS "RA", s.dec as "DEC",\n')
        outfile.write('s.psfmag_g AS "MAG_PSF_G",\n')
        outfile.write('s.psfmagerr_g AS "MAGERR_PSF_G",\n')
        outfile.write('s.psfmag_g - s.extinction_g AS "MAG_PSF_SFD_G",\n')
        outfile.write('s.psfmag_r AS "MAG_PSF_R",\n')
        outfile.write('s.psfmagerr_r AS "MAGERR_PSF_R",\n')
        outfile.write('s.psfmag_r - s.extinction_r AS "MAG_PSF_SFD_R",\n')
        outfile.write('s.psfmag_i AS "MAG_PSF_I",\n')
        outfile.write('s.psfmagerr_i AS "MAGERR_PSF_I",\n')
        outfile.write('s.psfmag_i - s.extinction_i AS "MAG_PSF_SFD_I"\n')
        outfile.write('INTO MyDB.%s\n' % (db))
        outfile.write('FROM %s.StarTag as s\n'%(self.release))
        outfile.write('WHERE s.ra > %.7f AND s.ra < %.7f\n' % (ra_min,ra_max))
        outfile.write('AND s.dec > %.7f AND s.dec < %.7f\n' % (dec_min,dec_max))
        outfile.write('AND s.clean = 1\n')
        outfile.close()

    def query(self,dbase,task,query):
        logger.info("Running query...")
        cmd = "java -jar casjobs.jar run -t %s -n %s -f %s" % (dbase,task,query)
        logger.info(cmd)
        ret = subprocess.check_output(cmd,shell=True,stderr=subprocess.STDOUT) 
        if 'ERROR:' in ret:
            raise subprocess.CalledProcessError(1,cmd,ret)
        return ret
        
    def extract(self, table):
        logger.info("Extracting...")
        cmd = "java -jar casjobs.jar extract -u -F -a FITS -b %s" % (table)
        logger.info(cmd)
        retval = subprocess.check_output(cmd,shell=True)

        url = None
        match = re.search("(http\:\/\/.*\.fit)",retval)
        if (match is not None) :
            url = match.group(0)
        else:
            logger.info("URL not found...here's the output")
            logger.info(retval)
        return url

    def wget(self,url,outfile=None):
        logger.info("Downloading %s\n" % (url))
        if outfile is not None: cmd = "wget -O %s %s" % (outfile,url)
        else:                   cmd = "wget %s" % (url)
        logger.info(cmd)
        return subprocess.check_output(cmd,shell=True)

    def drop(self, table):
        logger.info("Dropping...")
        cmd = "java -jar casjobs.jar execute -t MyDB -n \"drop query\" \"drop table %s\""%(table)
        logger.info(cmd)
        return subprocess.check_output(cmd,shell=True)

    def download(self, pixel, outdir=None):
        if outdir is None: outdir = './'
        else:              ugali.utils.shell.mkdir(outdir)
        sqldir = ugali.utils.shell.mkdir(os.path.join(outdir,'sql'))

        basename = self.basename + "_%04d"%pixel['name']
        sqlname = os.path.join(sqldir,basename+'.sql')
        dbname = basename+'_output'
        taskname = basename
        outfile = os.path.join(outdir,basename+".fits")
        if os.path.exists(outfile):
            logger.warning("Found %s; skipping..."%(outfile))
            return

        logger.info("\nDownloading pixel: %(name)i (ra=%(ra_min)g:%(ra_max)g,dec=%(dec_min)g:%(dec_max)g)"%(pixel))
        logger.info("Working on "+sqlname)
         
        self.generate_query(pixel['ra_min'],pixel['ra_max'],pixel['dec_min'],pixel['dec_max'],sqlname,dbname)

        try:
            self.query(self.release,taskname,sqlname)
        except subprocess.CalledProcessError, e:
            print e.output
            self.drop(dbname)
            raise e
        
        try:
            url = self.extract(dbname)
        except subprocess.CalledProcessError, e:
            self.drop(dbname)
            raise e
            
        if (url is not None):
            self.wget(url,outfile)

        self.drop(dbname)

    def upload(self, array, fields=None, table="MyDB", configfile=None):
        """
        Upload an array to a personal database using SOAP POST protocol.
        http://skyserver.sdss3.org/casjobs/services/jobs.asmx?op=UploadData
        """

        wsid=''
        password=''
        if configfile is None:
            configfile = "CasJobs.config"
        logger.info("Reading config file: %s"%configfile)
        lines = open(configfile,'r').readlines()
        for line in lines:
            k,v = line.strip().split('=')
            if k == 'wsid': wsid = v
            if k == 'password': password = v

        logger.info("Attempting to drop table: %s"%table)
        self.drop(table)
     
        SOAP_TEMPLATE = """
        <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
                         xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
                         xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
          <soap12:Body>
            <UploadData xmlns="http://Services.Cas.jhu.edu">
              <wsid>%s</wsid>
              <pw>%s</pw>
              <tableName>%s</tableName>
              <data>%s</data>
              <tableExists>%s</tableExists>
            </UploadData>
          </soap12:Body>
        </soap12:Envelope>
        """
     
        logger.info("Writing array...")
        s = StringIO.StringIO()
        np.savetxt(s,array,delimiter=',',fmt="%.10g")
        tb_data = ''
        if fields is not None: 
            tb_data += ','.join(f for f in fields)+'\n'
        tb_data += s.getvalue()
     
        message = SOAP_TEMPLATE % (wsid, password, table, tb_data, "false")
        
        #construct and send the header
        webservice = httplib.HTTP("skyserver.sdss3.org")
        webservice.putrequest("POST", "/casjobs/services/jobs.asmx")
        webservice.putheader("Host", "skyserver.sdss3.org")
        webservice.putheader("Content-type", "text/xml; charset=\"UTF-8\"")
        webservice.putheader("Content-length", "%d" % len(message))
        webservice.endheaders()
        logger.info("Sending SOAP POST message...")
        webservice.send(message)
         
        # get the response
        statuscode, statusmessage, header = webservice.getreply()
        print "Response: ", statuscode, statusmessage
        print "headers: ", header
        res = webservice.getfile().read()
        print res


    def run(self,pixfile,outdir=None):
        self.load_pixels(pixfile)
        for pixel in self.pixels:
            self.download(pixel,outdir)

    def inFootprint(self, ra, dec):
        basename = self.basename + '_coverage'
        sqlname = basename + '.sql'
        dbname = basename + '_output'
        task = basename
        outfile = basename+".fits"

        # Upload the (ra,dec) coordinates to casjobs
        table = "ra_dec"
        self.upload(np.array([ra,dec]).T, ['ra','dec'],table=table)

        # Query the database for the footprint
        query = open(sqlname,'w')
        query.write('SELECT dbo.fInFootprintEq(t.ra, t.dec, 0)\n')
        query.write('INTO MyDB.%s\n' % (dbname))
        query.write('FROM MyDB.%s AS t'%table)
        query.close()

        self.query(self.release,task,sqlname)
        url = self.extract(dbname)
        
        if (url is not None):
            self.wget(url,outfile)

        self.drop(table)
        self.drop(dbname)


    def footprint(self,nside):
        """
        Download the survey footprint for HEALpix pixels.
        """
        import healpy
        import ugali.utils.projector
        if nside > 2**9: raise Exception("Overflow error: nside must be <=2**9")
        pix = numpy.arange(healpy.nside2npix(nside),dtype='int')
        footprint = numpy.zeros(healpy.nside2npix(nside),dtype='bool')
        ra,dec = ugali.utils.projector.pixToAng(nside,pix)
        table_name = 'Pix%i'%nside
        self.upload(np.array([pix,ra,dec]).T, ['pix','ra','dec'], name=table_name)
        radius = healpy.nside2resol(nside_superpix,arcmin=True)

        query="""
        SELECT t.pix, dbo.fInFootprintEq(t.ra, t.dec, %g)
        FROM %s AS t
        """%(radius, table_name)

class DESDatabase(Database):
    ####################################
    ### !!! NOT FULLY IMPLEMENTED !!!###
    ####################################

    def __init__(self,pixfile,release='SVA1'):
        super(DESDatabase,self).__init__()
        self.release = release.lower()
        self.basename = "sdss_%s_photometry"%self.release
        self.load_pixels(pixfile)

    def generate_query(self, ra_min,ra_max,dec_min,dec_max,filename,db):
        # Preliminary and untested
        outfile = open(filename,"w")
        outfile.write('SELECT s.objID, s.ra AS "RA", s.dec as "DEC",\n')
        outfile.write('s.MAG_PSF_G,\n')
        outfile.write('s.MAGERR_PSF_G,\n')
        outfile.write('s.MAG_PSF_R,\n')
        outfile.write('s.MAGERR_PSF_R,\n')
        outfile.write('s.MAG_PSF_I,\n')
        outfile.write('s.MAGERR_PSF_I,\n')
        outfile.write("INTO MyDB.%s\n" % (db))
        outfile.write("FROM %s.COADD_OBJECTS as s\n"%(self.release))
        outfile.write("WHERE s.ra > %.7f AND s.ra < %.7f\n" % (ra_min,ra_max))
        outfile.write("AND s.dec > %.7f AND s.dec < %.7f\n" % (dec_min,dec_max))
        outfile.close()


if __name__ == "__main__":
    from optparse import OptionParser
    usage = "Usage: %prog  [options] pixels.txt"
    description = "Download dataset."
    parser = OptionParser(usage=usage,description=description)
    parser.add_option('--db',default='DR10',
                      help="Data set to download.")
    parser.add_option('-o','--outdir',default=None,
                      help="Output directory")
    (opts, args) = parser.parse_args()

    if len(args) == 0:
        args = [ None ]

    for arg in args:
        if opts.db == 'DR10':
            db = SDSSDatabase(release='DR10')
        elif opts.db == 'SVA1':
            pass
        db.run(pixfile=arg,outdir=opts.outdir)