"""
Tools for different procedure estimations
"""

import numpy as np
from scipy import sparse as SP
import scipy.optimize as op
import numpy.linalg as la
from pysal import lag_spatial
import copy


class RegressionProps:
    """
    Helper class that adds common regression properties to any regression
    class that inherits it.  It takes no parameters.  See BaseOLS for example
    usage.

    Parameters
    ----------

    Attributes
    ----------
    utu     : float
              Sum of the squared residuals
    sig2n    : float
              Sigma squared with n in the denominator
    sig2n_k : float
              Sigma squared with n-k in the denominator
    vm      : array
              Variance-covariance matrix (kxk)
    mean_y  : float
              Mean of the dependent variable
    std_y   : float
              Standard deviation of the dependent variable
              
    """

    @property
    def utu(self):
        if 'utu' not in self._cache:
            self._cache['utu'] = np.sum(self.u**2)
        return self._cache['utu']
    @property
    def sig2n(self):
        if 'sig2n' not in self._cache:
            self._cache['sig2n'] = self.utu / self.n
        return self._cache['sig2n']
    @property
    def sig2n_k(self):
        if 'sig2n_k' not in self._cache:
            self._cache['sig2n_k'] = self.utu / (self.n-self.k)
        return self._cache['sig2n_k']
    @property
    def vm(self):
        if 'vm' not in self._cache:
            self._cache['vm'] = np.dot(self.sig2, self.xtxi)  #LA which sig2?
        return self._cache['vm']
    
    @property
    def mean_y(self):
        if 'mean_y' not in self._cache:
            self._cache['mean_y']=np.mean(self.y)
        return self._cache['mean_y']
    @property
    def std_y(self):
        if 'std_y' not in self._cache:
            self._cache['std_y']=np.std(self.y, ddof=1)
        return self._cache['std_y']

def get_A1_het(S):
    """
    Builds A1 as in Arraiz et al [1]_

    .. math::

        A_1 = W' W - diag(w'_{.i} w_{.i})

    ...

    Parameters
    ----------

    S               : csr_matrix
                      PySAL W object converted into Scipy sparse matrix

    Returns
    -------

    Implicit        : csr_matrix
                      A1 matrix in scipy sparse format

    References
    ----------

    .. [1] Arraiz, I., Drukker, D. M., Kelejian, H., Prucha, I. R. (2010) "A
    Spatial Cliff-Ord-Type Model with Heteroskedastic Innovations: Small and
    Large Sample Results". Journal of Regional Science, Vol. 60, No. 2, pp.
    592-614.
    """
    StS = S.T * S   #LA set diagonal of StS to zero, that's it
    d = SP.spdiags([StS.diagonal()], [0], S.get_shape()[0], S.get_shape()[1])
    d = d.asformat('csr')
    return StS - d

def get_A1_hom(s, scalarKP=False):
    """
    Builds A1 for the spatial error GM estimation with homoscedasticity as in Drukker et al. [1]_ (p. 9).

    .. math::

        A_1 = \{1 + [n^{-1} tr(W'W)]^2\}^{-1} \[W'W - n^{-1} tr(W'W) I\]

    ...

    Parameters
    ----------

    s               : csr_matrix
                      PySAL W object converted into Scipy sparse matrix
    scalarKP        : boolean
                      Flag to include scalar corresponding to the first moment
                      condition as in Drukker et al. [1]_ (Defaults to False)

    Returns
    -------

    Implicit        : csr_matrix
                      A1 matrix in scipy sparse format
    References
    ----------

    .. [1] Drukker, Prucha, I. R., Raciborski, R. (2010) "A command for
    estimating spatial-autoregressive models with spatial-autoregressive
    disturbances and additional endogenous variables". The Stata Journal, 1,
    N. 1, pp. 1-13.      
    """
    n = s.shape[0]
    wpw = s.T * s
    twpw = np.sum(wpw.diagonal()) 
    e = SP.eye(n, n, format='csr')
    e.data = np.ones(n) * (twpw / n)
    num = wpw - e
    if not scalarKP:
        return num
    else:
        den = 1 + (twpw / n)**2
        return num / den

def get_A2_hom(s):
    """
    Builds A2 for the spatial error GM estimation with homoscedasticity as in
    Anselin (2011) [1]_ 

    .. math::

        A_2 = \dfrac{(W + W')}{2}

    ...

    Parameters
    ----------
    s               : csr_matrix
                      PySAL W object converted into Scipy sparse matrix
    Returns
    -------
    Implicit        : csr_matrix
                      A2 matrix in scipy sparse format
    References
    ----------

    .. [1] Anselin (2011) "GMM Estimation of Spatial Error Autocorrelation with and without Heteroskedasticity".
    """
    return (s + s.T) / 2.

def _moments2eqs(A1, s, u):
    '''
    Helper to compute G and g in a system of two equations as in
    the heteroskedastic error models from Drukker et al. [1]_
    ...

    Parameters
    ----------

    A1          : scipy.sparse.csr
                  A1 matrix as in the paper, different deppending on whether
                  it's homocedastic or heteroskedastic model

    s           : W.sparse
                  Sparse representation of spatial weights instance

    u           : array
                  Residuals. nx1 array assumed to be aligned with w
 
    Attributes
    ----------

    moments     : list
                  List of two arrays corresponding to the matrices 'G' and
                  'g', respectively.


    References
    ----------

    .. [1] Drukker, Prucha, I. R., Raciborski, R. (2010) "A command for
    estimating spatial-autoregressive models with spatial-autoregressive
    disturbances and additional endogenous variables". The Stata Journal, 1,
    N. 1, pp. 1-13.
    '''
    n = s.shape[0]
    A1u = A1 * u
    wu = s * u
    g1 = np.dot(u.T, A1u)
    g2 = np.dot(u.T, wu)   #LA use 1/2 (W + W') for A2
    g = np.array([[g1][0][0],[g2][0][0]]) / n

    G11 = np.dot(u.T, (A1 + A1.T) * wu) #LA use eqn (38) (39)
    G12 = -np.dot(wu.T * A1, wu)
    G21 = np.dot(u.T, (s + s.T) * wu)
    G22 = -np.dot(wu.T, (s * wu))
    G = np.array([[G11[0][0],G12[0][0]],[G21[0][0],G22[0][0]]]) / n
    return [G, g]

def optim_moments(moments_in, vcX=np.array([0])):
    """
    Optimization of moments
    ...

    Parameters
    ----------

    moments     : Moments
                  Instance of gmm_utils.moments_het with G and g
    vcX         : array
                  Optional. 2x2 array with the Variance-Covariance matrix to be used as
                  weights in the optimization (applies Cholesky
                  decomposition). Set empty by default.

    Returns
    -------
    x, f, d     : tuple
                  x -- position of the minimum
                  f -- value of func at the minimum
                  d -- dictionary of information from routine
                        d['warnflag'] is
                            0 if converged
                            1 if too many function evaluations
                            2 if stopped for another reason, given in d['task']
                        d['grad'] is the gradient at the minimum (should be 0 ish)
                        d['funcalls'] is the number of function calls made
    """
    moments = copy.deepcopy(moments_in)
    if vcX.any():
        Ec = np.transpose(la.cholesky(la.inv(vcX)))
        moments[0] = np.dot(Ec,moments_in[0])
        moments[1] = np.dot(Ec,moments_in[1])
    if moments[0].shape[0] == 2:
        optim_par = lambda par: foptim_par(np.array([[float(par[0]),float(par[0])**2.]]).T,moments)
        start = [0.0]
        bounds=[(-1.0,1.0)]
    if moments[0].shape[0] == 3:
        optim_par = lambda par: foptim_par(np.array([[float(par[0]),float(par[0])**2.,par[1]]]).T,moments)
        start = [0.0,0.0]
        bounds=[(-1.0,1.0),(0,None)]        
    lambdaX = op.fmin_l_bfgs_b(optim_par,start,approx_grad=True,bounds=bounds)
    return lambdaX[0][0]

def foptim_par(par,moments):
    """ 
    Preparation of the function of moments for minimization
    ...

    Parameters
    ----------

    lambdapar       : float
                      Spatial autoregressive parameter
    moments         : list
                      List of Moments with G (moments[0]) and g (moments[1])

    Returns
    -------

    minimum         : float
                      sum of square residuals (e) of the equation system 
                      moments.g - moments.G * lambdapar = e
    """
    vv=np.dot(moments[0],par)
    vv2=vv-moments[1]             #LA - should be moments[1] - vv? doesn't matter in the end
    return sum(vv2**2)

def get_spFilter(w,lamb,sf):
    '''
    Compute the spatially filtered variables
    
    Parameters
    ----------
    w       : weight
              PySAL weights instance  
    lamb    : double
              spatial autoregressive parameter
    sf      : array
              the variable needed to compute the filter
    Returns
    --------
    rs      : array
              spatially filtered variable
    
    Examples
    --------

    >>> import numpy as np
    >>> import pysal
    >>> db=pysal.open("examples/columbus.dbf","r")
    >>> y = np.array(db.by_col("CRIME"))
    >>> y = np.reshape(y, (49,1))
    >>> w=pysal.open("examples/columbus.GAL").read()        
    >>> solu = get_spFilter(w,0.5,y)
    >>> print solu[0:5]
    [[  -8.9882875]
     [ -20.5685065]
     [ -28.196721 ]
     [ -36.9051915]
     [-111.1298   ]]

    '''        
    return sf - lamb * (w.sparse * sf)

def get_lags(w, x, w_lags):
    '''
    Calculates a given order of spatial lags and all the smaller orders

    Parameters
    ----------
    w       : weight
              PySAL weights instance
    x       : array
              nxk arrays with the variables to be lagged  
    w_lags  : integer
              Maximum order of spatial lag

    Returns
    --------
    rs      : array
              nxk*(w_lags+1) array with original and spatially lagged variables

    '''
    lag = lag_spatial(w, x)
    spat_lags = lag
    for i in range(w_lags-1):
        lag = lag_spatial(w, lag)
        spat_lags = np.hstack((spat_lags, lag))
    return spat_lags

def inverse_prod(w, data, scalar, post_multiply=False, inv_method="power_exp", threshold=0.0000000001, max_iterations=None):
    """ 

    Parameters
    ----------

    w               : Pysal W object
                      nxn Pysal spatial weights object 

    data            : Numpy array
                      nx1 vector of data
    
    scalar          : float
                      Scalar value (typically rho or lambda)

    post_multiply   : boolean
                      If True then post-multiplies the data vector by the
                      inverse of the spatial filter, if false then
                      pre-multiplies.
    inv_method      : string
                      If "regular" uses the inverse of W (slow);
                      If "power_exp" uses the power expansion method (default)

    threshold       : float
                      Test value to stop the iterations. Test is against
                      sqrt(increment' * increment), where increment is a
                      vector representing the contribution from each
                      iteration.

    max_iterations  : integer
                      Maximum number of iterations for the expansion.   

    Examples
    --------

    >>> import numpy, pysal
    >>> import numpy.linalg as la
    >>> np.random.seed(10)
    >>> w = pysal.lat2W(5, 5)
    >>> w.transform = 'r'
    >>> data = np.random.randn(w.n)
    >>> data.shape = (w.n, 1)
    >>> rho = 0.4
    >>> inv_pow = power_expansion(w, data, rho)
    >>> # regular matrix inverse
    >>> matrix = np.eye(w.n) - (rho * w.full()[0])
    >>> matrix = la.inv(matrix)
    >>> inv_reg = np.dot(matrix, data)
    >>> np.allclose(inv_pow, inv_reg, atol=0.0001)
    True
    >>> inv_cg = inverse_cg(w, data, rho)
    >>> # test the transpose version
    >>> inv_pow = power_expansion(w, data, rho, post_multiply=True)
    >>> inv_reg = np.dot(data.T, matrix)
    >>> np.allclose(inv_pow, inv_reg, atol=0.0001)
    True

    """                      
    if inv_method=="power_exp":
        inv_prod = power_expansion(w, data, scalar, post_multiply=post_multiply,\
                threshold=threshold, max_iterations=max_iterations)
    elif inv_method=="regular":
        matrix = la.inv(np.eye(w.n) - (scalar * w.full()[0]))
        if post_multiply:
            inv_prod = np.dot(data.T, matrix)
        else:
            inv_prod = np.dot(matrix, data)
    else:
        raise Exception, "Invalid method selected for inversion."
    return inv_prod

def power_expansion(w, data, scalar, post_multiply=False, threshold=0.0000000001, max_iterations=None):
    """
    Compute the inverse of a matrix using the power expansion (Leontief
    expansion).  General form is:
    
        .. math:: 
            x &= (I - \rho W)^{-1}v = [I + \rho W + \rho^2 WW + \dots]v \\
              &= v + \rho Wv + \rho^2 WWv + \dots

    Examples
    --------
    Tests for this function are in inverse_prod()

    """
    if post_multiply:
        lag = rev_lag_spatial
        data = data.T
    else:
        lag = lag_spatial
    running_total = copy.copy(data)
    increment = copy.copy(data)
    count = 1
    test = 10000000
    if max_iterations == None:
        max_iterations = 10000000
    while test > threshold and count <= max_iterations:
        increment = lag(w, scalar*increment)
        running_total += increment
        test = la.norm(increment)
        count += 1
    return running_total

def rev_lag_spatial(w, y):
    """
    Helper function for power_expansion.  This reverses the usual lag operator
    (pysal.lag_spatial) to post-multiply a vector by a sparse W.

    Parameters
    ----------

    w : W
        weights object
    y : array
        variable to take the lag of (note: assumed that the order of y matches
        w.id_order)

    Returns
    -------

    yw : array
         array of numeric values

    Examples
    --------
    Tests for this function are in inverse_prod()

    """
    return y * w.sparse

def set_endog(y, x, w, yend, q, constant, w_lags, lag_q):
    # Create spatial lag of y
    yl = lag_spatial(w, y)
    if issubclass(type(yend), np.ndarray):  # spatial and non-spatial instruments
        if lag_q:
            lag_vars = np.hstack((x, q))
        else:
            lag_vars = x
        spatial_inst = get_lags(w ,lag_vars, w_lags)
        q = np.hstack((q, spatial_inst))
        yend = np.hstack((yend, yl))
    elif yend == None: # spatial instruments only
        q = get_lags(w, x, w_lags)
        yend = yl
    else:
        raise Exception, "invalid value passed to yend"
    return yend, q

def iter_msg(iteration,max_iter):
    if iteration==max_iter:
        iter_stop = "Maximum number of iterations reached."
    else:
        iter_stop = "Convergence threshold (epsilon) reached."
    return iter_stop

def _test():
    import doctest
    doctest.testmod()

if __name__ == '__main__':
    _test() 