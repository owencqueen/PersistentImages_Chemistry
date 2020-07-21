from ripser import Rips
from ripser import ripser
rips = Rips()
from sklearn.base import TransformerMixin
import numpy as np
import collections
from itertools import product
import collections
import pandas as pd
from scipy.stats import multivariate_normal as mvn
from scipy.stats import norm
import scipy.spatial as spatial
import matplotlib.pyplot as plt

from elements import ELEMENTS


def Makexyzdistance(t):
    '''
    distance, element = Makexyzdistance(t)

    Purpose: Reads in x, y, z data for atoms in a chemical 
    compound and returns their distances and the name of the compound.

    Parameters:
    -----------
    t: name of source file for coordinate data for a compound
        - See documentation's specifications for file structure
        - File contains x, y, z coordinates for each atom in compound

    Return Values:
    --------------
    Distance: distance matrix for every atom in the compound

    element: name of the element being read 
    '''
    element = np.loadtxt(t, dtype=str, usecols=(0,), skiprows=2)
    x = np.loadtxt(t, dtype=float, usecols=(1), skiprows=2)
    y = np.loadtxt(t, dtype=float, usecols=(2), skiprows=2)
    z = np.loadtxt(t, dtype=float, usecols=(3), skiprows=2)

    # Initialize distance matrix
    Distance = np.zeros(shape = (len(x),len(x)))

    for i in range(0, len(x)): # Fill distance matrix

       # Make an array for each atom
        for j in range(0, len(x)):

        #Calculate the distance between every atom
            Distance[i][j] = np.sqrt(  ((x[i]-x[j])**2)  + ((y[i]-y[j])**2)  \
                + ((z[i]-z[j]) **2)  )

    return [Distance, element]

__all__ = ["PersImage"]

class PersImage(TransformerMixin):
    """ Initialize a persistence image generator.

    Parameters
    -----------

    pixels : pair of ints like (int, int)
        Tuple representing number of pixels in return image along x and y axis.
    spread : float
        Standard deviation of gaussian kernel
    specs : dict
        Parameters for shape of image with respect to diagram domain. This is used if you would like images to have a particular range. Shaped like 
        ::
        
            {
                "maxBD": float,
                "minBD": float
            }

    kernel_type : string or ...
        TODO: Implement this feature.
        Determine which type of kernel used in the convolution, or pass in custom kernel. Currently only implements Gaussian.
    weighting_type : string or ...
        TODO: Implement this feature.
        Determine which type of weighting function used, or pass in custom weighting function.
        Currently only implements linear weighting.


    Usage
    ------


    """

    def __init__(
        self,
        pixels=(20, 20),
        spread=None,
        specs=None,
        kernel_type="gaussian",
        weighting_type="linear",
        verbose=True,
    ):

        self.specs = specs
        self.kernel_type = kernel_type
        self.weighting_type = weighting_type
        self.spread = spread
        self.nx, self.ny = pixels

        if verbose: # Prints parameters for user to see if verbose
            print(
                'PersImage(pixels={}, spread={}, specs={}, kernel_type="{}", weighting_type="{}")'.format(
                    pixels, spread, specs, kernel_type, weighting_type
                )
            )

    def transform(self, diagrams):
        """ Convert diagram or list of diagrams to a persistence image.

        Parameters
        -----------

        diagrams : list of or singleton diagram, list of pairs. [(birth, death)]
            - Persistence diagrams to be converted to persistence images. 
            - It is assumed they are in (birth, death) format. 
            - Can input a list of diagrams or a single diagram.
        """

        # if diagram is empty, return empty image
        if len(diagrams) == 0:
            return np.zeros((self.nx, self.ny))

        # if first entry of first entry is not iterable, then diagrams is 
        #   singular and we need to make it a list of diagrams
        try:
            singular = not isinstance(diagrams[0][0], collections.Iterable)
        except IndexError:
            singular = False

        if singular: # Make diagrams into a list of diagrams
            diagrams = [diagrams]

        # Copy diagrams to avoid changing original input
        dgs = [np.copy(diagram) for diagram in diagrams]

        # Converts each diagram to langscapes
        landscapes = [PersImage.to_landscape(dg) for dg in dgs]

        if not self.specs: # Set specs for diagram if not given
            self.specs = {
                "maxBD": np.max([np.max(np.vstack((landscape, np.zeros((1, 2))))) 
                                 for landscape in landscapes] + [0]),
                "minBD": np.min([np.min(np.vstack((landscape, np.zeros((1, 2))))) 
                                 for landscape in landscapes] + [0]),
            }

        imgs = [self._transform(dgm) for dgm in landscapes]

        # Make sure we return one item.
        if singular:
            imgs = imgs[0]

        return imgs

    def _transform(self, landscape):

        # Define an NxN grid over our landscape
        maxBD = self.specs["maxBD"]
        minBD = min(self.specs["minBD"], 0)  # at least show 0, maybe lower

        # Same bins in x and y axis
        dx = maxBD / (self.ny)
        xs_lower = np.linspace(minBD, maxBD, self.nx)
        xs_upper = np.linspace(minBD, maxBD, self.nx) + dx

        ys_lower = np.linspace(0, maxBD, self.ny)
        ys_upper = np.linspace(0, maxBD, self.ny) + dx

        weighting = self.weighting(landscape)

        # Define zeros
        img = np.zeros((self.nx, self.ny))
        
        # Implement this as a `summed-area table` - it'll be way faster
        
        if np.size(landscape,1) == 2:
            
            spread = self.spread if self.spread else dx
            for point in landscape:
                x_smooth = norm.cdf(xs_upper, point[0], spread) - norm.cdf(
                    xs_lower, point[0], spread
                )
                y_smooth = norm.cdf(ys_upper, point[1], spread) - norm.cdf(
                    ys_lower, point[1], spread
                )
                img += np.outer(x_smooth, y_smooth) * weighting(point)
            img = img.T[::-1]
            return img
        else:
            spread = self.spread if self.spread else dx
            for point in landscape:
                x_smooth = norm.cdf(xs_upper, point[0], point[2]*spread) - norm.cdf(
                    xs_lower, point[0], point[2]*spread
                )
                y_smooth = norm.cdf(ys_upper, point[1], point[2]*spread) - norm.cdf(
                    ys_lower, point[1], point[2]*spread
                )
                img += np.outer(x_smooth, y_smooth) * weighting(point)
            img = img.T[::-1]
            return img

    def weighting(self, landscape=None):
        """ Define a weighting function, 
                for stability results to hold, the function must be 0 at y=0.    
        """

        # TODO: Implement a logistic function
        # TODO: use self.weighting_type to choose function

        if landscape is not None:
            if len(landscape) > 0:
                maxy = np.max(landscape[:, 1])
            else: 
                maxy = 1

        def linear(interval):
            # linear function of y such that f(0) = 0 and f(max(y)) = 1
            d = interval[1]
            return (1 / maxy) * d if landscape is not None else d

        def pw_linear(interval):
            """ This is the function defined as w_b(t) in the original PI paper

                Take b to be maxy/self.ny to effectively zero out the bottom pixel row
            """

            t = interval[1]
            b = maxy / self.ny

            if t <= 0:
                return 0
            if 0 < t < b:
                return t / b
            if b <= t:
                return 1

        return linear

    def kernel(self, spread=1):
        """ This will return whatever kind of kernel we want to use.
            Must have signature (ndarray size NxM, ndarray size 1xM) -> ndarray size Nx1

        Parameters:
        -----------
        spread: variance/covariance for the kernel
        """
        # TODO: use self.kernel_type to choose function

        def gaussian(data, pixel):
            return mvn.pdf(data, mean = pixel, cov = spread)

        return gaussian

    @staticmethod
    def to_landscape(diagram):
        """ Convert a diagram to a landscape
            (birth, death) -> (birth, death-birth)
        """
        diagram[:, 1] -= diagram[:, 0]

        return diagram

    def show(self, imgs, ax=None):
        """ 
        Visualize the persistence image
        
        Parameters:
        -----------
        imgs: persistence images to show
        ax: Axes for a pyplot
            - Providing this is optional
        """

        ax = ax or plt.gca() # Get current axis if none is given

        # Need to convert imgs into a list if not already
        if type(imgs) is not list:
            imgs = [imgs]

        for i, img in enumerate(imgs):
            ax.imshow(img, cmap=plt.get_cmap("plasma"))
            ax.axis("off")
            

def VariancePersistv1(Filename, pixelx = 100, pixely = 100, myspread = 2, 
                        myspecs = {"maxBD": 2, "minBD": 0}, showplot = True):
    #Generate distance matrix and elementlist
    D,elements = Makexyzdistance(Filename)
    
    #Generate data for persistence diagram
    a = ripser(D,distance_matrix=True)

    #Make the birth,death for h0 and h1
    points = (a['dgms'][0][0:-1,1])
    pointsh1 = (a['dgms'][1])
    diagrams = rips.fit_transform(D, distance_matrix=True) 

    #Find pair electronegativies
    eleneg=list()
    for index in points:
        c = np.where(np.abs((index-a['dperm2all'])) < .00000015)[0]

        eleneg.append(np.abs(ELEMENTS[elements[c[0]]].eleneg - ELEMENTS[elements[c[1]]].eleneg))
    
    #new matrix with electronegativity variance in third row, completely empirical
    #Formula (| EN1 - EN2| + .4) / 10
    
    h0matrix = np.hstack(((diagrams[0][0:-1,:], np.reshape(((np.array(eleneg)+.4)/10 ), (np.size(eleneg),1)))))
    buffer = np.full((diagrams[1][:,0].size,1), 0.05)
    h1matrix = np.hstack((diagrams[1],buffer))
    
    #combine them
    Totalmatrix = np.vstack((h0matrix,h1matrix))
    pim = PersImage(pixels=[pixelx,pixely], spread=myspread, specs=myspecs, verbose=False)
    imgs = pim.transform(Totalmatrix)
    
    if showplot == True:
        pim.show(imgs)
        plt.show()

    return np.array(imgs.flatten())



def VariancePersist(Filename, pixelx=100, pixely=100, myspread=2, 
                    myspecs={"maxBD": 2, "minBD":0}, showplot=True):
    
    #Generate distance matrix and elementlist
    D, elements = Makexyzdistance(Filename)
   
    #Generate data for persistence diagram
    a = ripser(D,distance_matrix=True)

    #Make the birth,death for h0 and h1
    points = (a['dgms'][0][0:-1,1])
    pointsh1 = (a['dgms'][1])
    diagrams = rips.fit_transform(D, distance_matrix=True)

    #Find pair electronegativies
    eleneg=list()

    for index in points:
        c = np.where(np.abs((index-a['dperm2all'])) < .00000015)[0]

        eleneg.append(np.abs(ELEMENTS[elements[c[0]]].eleneg - ELEMENTS[elements[c[1]]].eleneg))
   
   
    h0matrix = np.hstack(((diagrams[0][0:-1,:], np.reshape((((np.array(eleneg)*1.05)+.01)/10 ), (np.size(eleneg),1)))))
    buffer = np.full((diagrams[1][:,0].size,1), 0.05)
    h1matrix = np.hstack((diagrams[1],buffer))
    
    #combine them
    Totalmatrix = np.vstack((h0matrix,h1matrix))
    pim = PersImage(pixels=[pixelx,pixely], spread=myspread, specs=myspecs, verbose=False)
    imgs = pim.transform(Totalmatrix)
   
    if showplot == True:
        pim.show(imgs)
        plt.show()
    return np.array(imgs.flatten())


def PersDiagram(xyz, lifetime=True):
    '''
    PersDiagram(xyz, lifetime)

    Purpose: Creates a visual representation for a persistence diagram

    Parameters:
    -----------



    '''
    plt.rcParams["font.family"] = "Times New Roman"
    D,elements = Makexyzdistance(xyz)
    data = ripser(D,distance_matrix=True)
    rips = Rips()
    rips.transform(D, distance_matrix=True)
    rips.dgms_[0]=rips.dgms_[0][0:-1]
    rips.plot(show=False, lifetime=lifetime, labels=['Connected Components','Holes'])
    L = plt.legend()
    plt.setp(L.texts, family="Times New Roman")
    plt.rcParams["font.family"] = "Times New Roman"

def GeneratePI(xyz, savefile=False, pixelx=100, pixely=100, myspread=2, bounds={"maxBD": 3, "minBD":-0.1}):
    X = VariancePersistv1(xyz, pixelx=100, pixely=100, myspread=2 ,myspecs=bounds, showplot=False)
    pim = PersImage(pixels=[pixelx,pixely], spread=myspread, specs=bounds, verbose=False)

    img = X.reshape(pixelx,pixely)
    pim.show(img)
    if savefile==True:
        plt.imsave(xyz+'_img.png',img, cmap=plt.get_cmap("plasma"), dpi=200)

