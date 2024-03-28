import os

APP_NAME = 'SoggyVision'

APP_DIR = os.path.normpath(os.path.join(os.path.expanduser('~'), APP_NAME))
CAL_DIR = os.path.join(APP_DIR,'calibrations')
DB_DIR = os.path.join(APP_DIR,'db')
EXPORT_DIR = os.path.join(APP_DIR,'data')

SV_VERSION = '0.0.1'
SV_REPO = f'https://github.com/IanTBlack/{APP_NAME}'
SV_ISSUES = f'https://github.com/IanTBlack/{APP_NAME}/issues'
SV_DISCUSSION = f'https://github.com/IanTBlack/{APP_NAME}/discussion'


def build_directories():
    for _dir in [APP_DIR, CAL_DIR, DB_DIR, EXPORT_DIR]:
        os.makedirs(_dir, exist_ok = True)
        if not os.path.isdir(_dir):
            raise NotADirectoryError(_dir)

def wavelength_to_rgb(wavelength, gamma=0.5):

    '''This converts a given wavelength of light to an
    approximate RGB color value. The wavelength must be given
    in nanometers in the range from 380 nm through 750 nm
    (789 THz through 400 THz).
    Based on code by Dan Bruton
    http://www.physics.sfasu.edu/astro/color/spectra.html
    '''

    wavelength = float(wavelength)
    if wavelength >= 380 and wavelength <= 440:
        attenuation = 0.3 + 0.7 * (wavelength - 380) / (440 - 380)
        R = ((-(wavelength - 440) / (440 - 380)) * attenuation) ** gamma
        G = 0.0
        B = (1.0 * attenuation) ** gamma
    elif wavelength >= 440 and wavelength <= 490:
        R = 0.0
        G = ((wavelength - 440) / (490 - 440)) ** gamma
        B = 1.0
    elif wavelength >= 490 and wavelength <= 510:
        R = 0.0
        G = 1.0
        B = (-(wavelength - 510) / (510 - 490)) ** gamma
    elif wavelength >= 510 and wavelength <= 580:
        R = ((wavelength - 510) / (580 - 510)) ** gamma
        G = 1.0
        B = 0.0
    elif wavelength >= 580 and wavelength <= 645:
        R = 1.0
        G = (-(wavelength - 645) / (645 - 580)) ** gamma
        B = 0.0
    elif wavelength >= 645 and wavelength <= 760:
        attenuation = 0.3 + 0.7 * (750 - wavelength) / (750 - 645)
        R = (1.0 * attenuation) ** gamma
        G = 0.0
        B = 0.0
    else:
        R = 0.0
        G = 0.0
        B = 0.0
    R *= 255
    G *= 255
    B *= 255
    return (int(R), int(G), int(B))