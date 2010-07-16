import numpy as np
import numpy.linalg as la
import ols as OLS

class TwoSLS(OLS.OLS):
    """
    2SLS class for end-user (gives back only results and diagnostics)
    """
    def __init__(self):



        # Need to check the shape of user input arrays, and report back descriptive
        # errors when necessary
        pass

class TwoSLS_dev(OLS.OLS_dev):
    """
    2SLS class to do all the computations

    NOTE: no consistency checks
    
    Maximal Complexity: 

    Parameters
    ----------

    x           : array
                  nxk array of independent variables, including endogenous
                  variables (assumed to be aligned with y)
    y           : array
                  nx1 array of dependent variable
    h           : array
                  nxl array of instruments; typically this includes all
                  exogenous variables from x and instruments
    constant    : boolean
                  If true it appends a vector of ones to the independent variables
                  to estimate intercept (set to True by default)

    Attributes
    ----------

    x           : array
                  nxk array of independent variables (assumed to be aligned with y)
    y           : array
                  nx1 array of dependent variable
    h           : array
                  nxl array of instruments
    betas       : array
                  kx1 array with estimated coefficients
    xt          : array
                  kxn array of transposed independent variables
    xtx         : array
                  kxk array
    xtxi        : array
                  kxk array of inverted xtx
    u           : array
                  nx1 array of residuals (based on original x matrix)
    predy       : array
                  nx1 array of predicted values (based on original x matrix)
    n           : int
                  Number of observations
    k           : int
                  Number of variables
    utu         : float
                  Sum of the squared residuals
    sig2        : float
                  Sigma squared with n in the denominator
    sig2n_k     : float
                  Sigma squared with n-k in the denominator
    vm          : array
                  Variance-covariance matrix (kxk)
    mean_y      : float
                  Mean of the dependent variable
    std_y       : float
                  Standard deviation of the dependent variable


    Examples
    --------

    >>> import numpy as np
    >>> import pysal
    >>> db=pysal.open("examples/columbus.dbf","r")
    >>> y = np.array(db.by_col("CRIME"))
    >>> y = np.reshape(y, (49,1))
    >>> X = []
    >>> X.append(db.by_col("INC"))
    >>> X.append(db.by_col("HOVAL"))
    >>> X = np.array(X).T
    >>> # instrument for HOVAL with DISCBD
    >>> h = []
    >>> h.append(db.by_col("INC"))
    >>> h.append(db.by_col("DISCBD"))
    >>> h = np.array(h).T
    >>> reg=TwoSLS_dev(X,y,h)
    >>> reg.betas
    array([[ 88.46579584],
           [  0.5200379 ],
           [ -1.58216593]])
    
    """
    def __init__(self, x, y, h, constant=True):
        if constant:
            x = np.hstack((np.ones(y.shape),x))
            z = np.hstack((np.ones(y.shape),h))
        else:
            z = h
        ztz = np.dot(z.T,z)
        ztzi = la.inv(ztz)
        ztx = np.dot(z.T, x)
        ztzi_ztx = np.dot(ztzi, ztx)
        x_hat = np.dot(z, ztzi_ztx)          # x_hat = Z(Z'Z)^-1 Z'X
        OLS.OLS_dev.__init__(self, x_hat, y, constant=False)
        self.xptxpi = self.xtxi              # using predicted x (xp)
        self.set_x(x)  # reset x, xtx and xtxi attributes to use original data
        self.predy = np.dot(x, self.betas)   # using original data
        self.u = y - self.predy              # using original data
        self.h = h

    @property
    def vm(self):
        if 'vm' not in self._cache:
            self._cache['vm'] = np.dot(self.sig2, self.xtxi)
        return self._cache['vm']
    
    

def _test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    _test()



