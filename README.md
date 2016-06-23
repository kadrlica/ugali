OVERVIEW
--------

[![Build](https://img.shields.io/travis/kadrlica/ugali.svg)](https://travis-ci.org/kadrlica/ugali)
[![Release](https://img.shields.io/github/tag/kadrlica/ugali.svg)](https://github.com/kadrlica/ugali/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/kadrlica/ugali)

The ultra-faint galaxy likelihood (UGaLi) toolkit provides a set of python classes and functions developed for maximum-likelihood-based studies of Milky Way satellite galaxies. The primary inputs are stellar object catalogs derived from optical photometric surveys and the coverage masks of those surveys.

[Keith Bechtol](https://github.com/bechtol) & [Alex Drlica-Wagner](https://github.com/kadrlica)

USAGE EXAMPLES
--------------
Examples go here.

CODE REPOSITORY
---------------
* https://bitbucket.org/bechtol/ugali/
* https://github.com/kadrlica/ugali/

DEPENDENCIES
------------

### Python packages:
* [numpy](http://www.numpy.org/)
* [scipy](https://www.scipy.org/)
* [matplotlib](http://matplotlib.org/)
* [pyfits](http://www.stsci.edu/institute/software_hardware/pyfits)
* [healpy](https://github.com/healpy/healpy)
* [astropy](http://www.astropy.org/)
* [emcee](http://dan.iel.fm/emcee/current/)
* [pyyaml](http://pyyaml.org/)

### Mangle:
Not a strict dependency. Used to interface with masks produced by
the Dark Energy Survey Data Mangement group. Download and documentation 
available at http://space.mit.edu/~molly/mangle/

### Isochrones:
The ugali tools make use of a large library of stellar isochrones. These isochrones are derived from two different groups and are distributed as binary tarballs with releases of ugali.
* Padova isochrones (http://stev.oapd.inaf.it/cgi-bin/cmd)
* Dartmouth isochrones (http://stellar.dartmouth.edu/models/isolf_new.html)

CONVENTIONS
-----------

### Indexing:
array[index_z][index_y][index_x]

### Naming:
* package_name
* module_name.py
* ClassName
* functionName
* variable_name

ABBREVIATIONS
-------------
* IMF: initial mass function
* CMD: color-magnitude diagram
* ROI: region of interest
* PDF: probability distribution function
* LUT: look-up table
* LKHD: likelihood
