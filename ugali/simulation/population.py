"""
Tool to generate a population of simulated satellite properties.
"""

import numpy as np
import pylab
import pandas as pd

import ugali.utils.config
import ugali.utils.projector
import ugali.utils.skymap
import ugali.analysis.kernel
import ugali.observation.catalog
import ugali.isochrone

pylab.ion()

############################################################

def satellitePopulation(mask, nside_pix, n,
                        range_distance=[5., 500.],
                        range_stellar_mass=[1.e1, 1.e6],
                        range_r_physical=[1.e-3, 2.],
                        plot=False):
    """
    Create a population of n randomly placed satellites within a
    survey mask.  Satellites are distributed uniformly in
    log(distance) (kpc), uniformly in log(stellar_mass) (M_sol), and
    uniformly in physical half-light radius log(r_physical) (kpc). The
    ranges can be set by the user.

    Returns the simulated area (deg^2) as well as the lon (deg), lat
    (deg), distance modulus, stellar mass (M_sol), and half-light
    radius (deg) for each satellite

    Parameters:
    -----------
    mask      : the survey mask of available area
    nside_pix : coarse resolution npix for avoiding small gaps in survey
    n         : number of satellites to simulate
    range_distance     : heliocentric distance range (kpc)
    range_stellar_mass : stellar mass range (Msun)
    range_r_physical   : projected physical half-light radius (kpc)

    Returns:
    --------
    area, lon, lat, distance, stellar_mass, r_physical    
    """
    
    distance = 10**np.random.uniform(np.log10(range_distance[0]),
                                     np.log10(range_distance[1]),
                                     n)

    stellar_mass = 10**np.random.uniform(np.log10(range_stellar_mass[0]), 
                                         np.log10(range_stellar_mass[1]), 
                                         n)
    
    # Physical half-light radius (kpc)
    r_physical = 10**np.random.uniform(np.log10(range_r_physical[0]), 
                                       np.log10(range_r_physical[1]), 
                                       n)

    # Call positions last because while loop has a variable number of calls to np.random (thus not preserving seed information)
    lon, lat, simulation_area = ugali.utils.skymap.randomPositions(mask, nside_pix, n=n)

    #half_light_radius = np.degrees(np.arcsin(half_light_radius_physical \
    #                                         / ugali.utils.projector.distanceModulusToDistance(distance_modulus)))

    # One choice of theory prior
    #half_light_radius_physical = ugali.analysis.kernel.halfLightRadius(stellar_mass) # kpc
    #half_light_radius = np.degrees(np.arcsin(half_light_radius_physical \
    #                                               / ugali.utils.projector.distanceModulusToDistance(distance_modulus)))

    if plot:
        pylab.figure()
        #pylab.scatter(lon, lat, c=distance_modulus, s=500 * half_light_radius)
        #pylab.colorbar()
        pylab.scatter(lon, lat, edgecolors='none')
        xmin, xmax = pylab.xlim() # Reverse azimuthal axis
        pylab.xlim([xmax, xmin])
        pylab.title('Random Positions in Survey Footprint')
        pylab.xlabel('Longitude (deg)')
        pylab.ylabel('Latitude (deg)')

        pylab.figure()
        pylab.scatter(stellar_mass, ugali.utils.projector.distanceModulusToDistance(distance_modulus),
                      c=(60. * half_light_radius), s=500 * half_light_radius, edgecolors='none')
        pylab.xscale('log')
        pylab.yscale('log')
        pylab.xlim([0.5 * range_stellar_mass[0], 2. * range_stellar_mass[1]])
        pylab.colorbar()
        pylab.title('Half-light Radius (arcmin)')
        pylab.xlabel('Stellar Mass (arcmin)')
        pylab.ylabel('Distance (kpc)')

    return simulation_area, lon, lat, distance, stellar_mass, r_physical

############################################################

def satellitePopulationOrig(config, n,
                            range_distance_modulus=[16.5, 24.],
                            range_stellar_mass=[1.e2, 1.e5],
                            range_r_physical=[5.e-3, 1.],
                            mode='mask',
                            plot=False):
    """
    Create a population of n randomly placed satellites within a survey mask or catalog specified in the config file.
    Satellites are distributed uniformly in distance modulus, uniformly in log(stellar_mass) (M_sol), and uniformly in
    log(r_physical) (kpc). The ranges can be set by the user.

    Returns the simulated area (deg^2) as well as the
    lon (deg), lat (deg), distance modulus, stellar mass (M_sol), and half-light radius (deg) for each satellite
    """
    
    if type(config) == str:
        config = ugali.utils.config.Config(config)

    if mode == 'mask':
        mask_1 = ugali.utils.skymap.readSparseHealpixMap(config.params['mask']['infile_1'], 'MAGLIM')
        mask_2 = ugali.utils.skymap.readSparseHealpixMap(config.params['mask']['infile_2'], 'MAGLIM')
        input = (mask_1 > 0.) * (mask_2 > 0.)
    elif mode == 'catalog':
        catalog = ugali.observation.catalog.Catalog(config)
        input = np.array([catalog.lon, catalog.lat])
    
    lon, lat, simulation_area = ugali.utils.skymap.randomPositions(input,
                                                                   config.params['coords']['nside_likelihood_segmentation'],
                                                                   n=n)
    distance_modulus = np.random.uniform(range_distance_modulus[0], 
                                         range_distance_modulus[1], 
                                         n)
    stellar_mass = 10**np.random.uniform(np.log10(range_stellar_mass[0]), 
                                         np.log10(range_stellar_mass[1]), 
                                         n)
    
    half_light_radius_physical = 10**np.random.uniform(np.log10(range_half_light_radius_physical[0]), 
                                                       np.log10(range_half_light_radius_physical[0]), 
                                                       n) # kpc

    half_light_radius = np.degrees(np.arcsin(half_light_radius_physical \
                                             / ugali.utils.projector.distanceModulusToDistance(distance_modulus)))
    
    # One choice of theory prior
    #half_light_radius_physical = ugali.analysis.kernel.halfLightRadius(stellar_mass) # kpc
    #half_light_radius = np.degrees(np.arcsin(half_light_radius_physical \
    #                                               / ugali.utils.projector.distanceModulusToDistance(distance_modulus)))

    if plot:
        pylab.figure()
        #pylab.scatter(lon, lat, c=distance_modulus, s=500 * half_light_radius)
        #pylab.colorbar()
        pylab.scatter(lon, lat, edgecolors='none')
        xmin, xmax = pylab.xlim() # Reverse azimuthal axis
        pylab.xlim([xmax, xmin])
        pylab.title('Random Positions in Survey Footprint')
        pylab.xlabel('Longitude (deg)')
        pylab.ylabel('Latitude (deg)')

        pylab.figure()
        pylab.scatter(stellar_mass, ugali.utils.projector.distanceModulusToDistance(distance_modulus),
                      c=(60. * half_light_radius), s=500 * half_light_radius, edgecolors='none')
        pylab.xscale('log')
        pylab.yscale('log')
        pylab.xlim([0.5 * range_stellar_mass[0], 2. * range_stellar_mass[1]])
        pylab.colorbar()
        pylab.title('Half-light Radius (arcmin)')
        pylab.xlabel('Stellar Mass (arcmin)')
        pylab.ylabel('Distance (kpc)')

    return simulation_area, lon, lat, distance_modulus, stellar_mass, half_light_radius 

############################################################

def interpolate_absolute_magnitude():
    iso = ugali.isochrone.factory('Bressan2012',age=12,z=0.00010)

    stellar_mass,abs_mag = [],[]
    for richness in np.logspace(1,8,25):
        stellar_mass += [iso.stellar_mass()*richness]
        if stellar_mass[-1] < 1e3:
            abs_mag += [iso.absolute_magnitude_martin(richness)[0]]
        else:
            abs_mag += [iso.absolute_magnitude(richness)]

    return abs_mag,stellar_mass

def knownPopulation(dwarfs, mask, nside_pix, n):
    """ Sample parameters from a known population .
    
    Parameters
    ----------
    dwarfs : known dwarfs to sample at
    mask      : the survey mask of available area
    nside_pix : coarse resolution npix for avoiding small gaps in survey
    n         : number of satellites to simulate; will be broken into 
                n//len(dwarfs) per dwarf

    Returns
    -------
    area, lon, lat, distance, stellar_mass, r_physical    
    """
    # generated from the interpolation function above.
    abs_mag_interp = [5.7574, 4.5429, 3.5881, 2.7379, 1.8594, 0.9984, 0.0245, 
                    -0.851, -1.691, -2.495, -3.343, -4.072, -4.801, -5.530, 
                    -6.259, -6.988, -7.718, -8.447, -9.176, -9.905, -10.63, 
                    -11.36, -12.09, -12.82, -13.55][::-1]

    stellar_mass_interp = [2.363705510, 4.626579555, 9.055797468, 17.72529075, 
                    34.69445217, 67.90890082, 132.9209289, 260.1716878, 
                    509.2449149, 996.7663490, 1951.012421, 3818.798128, 
                    7474.693131, 14630.52917, 28636.94603, 56052.29096, 
                    109713.4910, 214746.8000, 420332.8841, 822735.1162, 
                    1610373.818, 3152051.957, 6169642.994, 12076100.01, 
                    23637055.10][::-1]

    if isinstance(dwarfs,str):
        dwarfs = pd.read_csv(dwarfs).to_records(index=False)

    nsim = n // len(dwarfs)
    nlast = nsim + n % len(dwarfs)

    import pdb; pdb.set_trace()
    
    print('Calculating coarse footprint mask...')
    coarse_mask = ugali.utils.skymap.coarseFootprint(mask, nside_pix)

    results = []
    for i,dwarf in enumerate(dwarfs):
        print(dwarf['name'])
        kwargs = dict()
        kwargs['range_distance']   = [dwarf['distance'],dwarf['distance']]
        r_physical = dwarf['r_physical']/1000.
        kwargs['range_r_physical'] = [r_physical,r_physical]
        stellar_mass = np.interp(dwarf['abs_mag'],abs_mag_interp,stellar_mass_interp)
        kwargs['range_stellar_mass'] = [stellar_mass, stellar_mass]      
        print("Generating population...")
        num = nsim if i < (len(dwarfs)-1) else nlast
        ret = satellitePopulation(coarse_mask, nside_pix, num, **kwargs)
        results += [ret[1:]]

    lon, lat, distance_modulus, stellar_mass, half_light_radius = np.hstack(results)
    return area, lon, lat, distance_modulus, stellar_mass, half_light_radius
