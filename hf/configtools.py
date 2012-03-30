
import ConfigParser
import os, hf, cherrypy, traceback, logging
import logging.config
from mako.lookup import TemplateLookup

def _getCfgInDirectory(dir):
    return sorted(filter(lambda x: x.lower().endswith(".cfg") and os.path.isfile(x), map(lambda x:os.path.join(dir,x), os.listdir(dir))))

def readConfigurationAndEnv():
    logger = logging.getLogger(__name__)
    '''
    Read configuration files for HappyFace from defaultconf directory and subsequently from
    the local HappyFace config directory. The HappyFace config is then accessible by hf.config
    
    After the default configuration is read, the environment variables are searched for
    HF_DEBUG (controls exception output on webpage, implies HF_LOGLEVEL=DEBUG), HF_LOGLEVEL
    and HF_WGETOPTIONS (extra global options)
    
    Also, read category and module config in hf.category.config and hf.module.config and create
    a template lookup object in hf.template_lookup with the appropriate paths from the configuration.
    '''
    defaults = {}
    
    hf.config = ConfigParser.ConfigParser(defaults=defaults)
    for file in _getCfgInDirectory(os.path.join(hf.hf_dir, "defaultconfig")):
        try:
            hf.config.read(file)
        except Exception, e:
            logger.exception("Cannot import default config '%s'" % file)
            raise
    if os.path.exists(hf.config.get("paths", "local_happyface_cfg_dir")):
        for file in _getCfgInDirectory(os.path.join(hf.hf_dir, hf.config.get("paths", "local_happyface_cfg_dir"))):
            try:
                hf.config.read(file)
            except Exception, e:
                logger.exception("Cannot import config '%s'" % file)
                raise
    else:
        logger.info('Configuration directory does not exist, use only defaults')
    
    directories = [hf.config.get("paths", "hf_template_dir"), hf.config.get("paths", "module_template_dir")]
    directories = map(lambda x: os.path.join(hf.hf_dir, x), directories)
    hf.template_lookup = TemplateLookup(directories=directories, module_directory=hf.config.get("paths", "template_cache_dir"))
    
    if not os.path.exists(hf.config.get("paths", "category_cfg_dir")):
        raise hf.exceptions.ConfigError("Category config directory not found")
    if not os.path.exists(hf.config.get("paths", "module_cfg_dir")):
        raise hf.exceptions.ConfigError("Module config directory not found")
    
    hf.category.config = ConfigParser.ConfigParser()
    for dirpath, dirnames, filenames in os.walk(hf.config.get("paths", "category_cfg_dir")):
        for filename in filenames:
            if filename.endswith(".cfg"):
                hf.category.config.read(os.path.join(dirpath, filename))
                cherrypy.engine.autoreload.files.add(os.path.join(dirpath, filename))
    
    hf.module.config = ConfigParser.ConfigParser(defaults=hf.module.ModuleBase.config_defaults)
    for dirpath, dirnames, filenames in os.walk(hf.config.get("paths", "module_cfg_dir")):
        for filename in filenames:
            if filename.endswith(".cfg"):
                hf.module.config.read(os.path.join(dirpath, filename))
                cherrypy.engine.autoreload.files.add(os.path.join(dirpath, filename))
                
def importModules():
    '''
    
    '''
    used_modules = []
    for category in hf.category.config.sections():
        conf = dict(hf.category.config.items(category))
        for module in conf["modules"].split(","):
            if len(module) == 0: continue
            if module in used_modules:
                raise hf.ConfigError("Module '%s' used second time in category '%s'" % (module, category))
            try:
                hf.module.tryModuleClassImport(hf.module.config.get(module, "module"))
            except ConfigParser.NoSectionError, e:
                raise hf.ConfigError("Referenced module %s from category %s was never configured" % (module, category))

def setupLogging(logging_cfg):
    """
    Setup the python logging module and apply loglevel from
    environment variables if specified.
    
    The argument to this function is the name of the configuration key
    in the 'paths' section containing the path to the loggin configuration.
    For the format of the config, please see the Python docs
    http://docs.python.org/library/logging.config.html#configuration-file-format
    
    If None is specified, console logging only is setup. This is particularily
    usefull for tools e.g. for migration or cleanup.
    
    The environment variable HF_LOGLEVEL can contain a level from DEFAULT, INFO,
    WARNING, ERROR or CRITICAL. If HF_DEBUG is set, HF_LOGLEVEL=DEBUG is implied.
    """
    if logging_cfg is None:
        logging.basicConfig(level=logging.WARNING)
    else:
        logging.config.fileConfig(hf.config.get("paths", logging_cfg), disable_existing_loggers=False)
    if "HF_LOGLEVEL" in os.environ:
        logging.root.setLevel(getattr(logging, os.environ["HF_LOGLEVEL"].upper()))
    if "HF_DEBUG" in os.environ:
        logging.root.setLevel(logging.DEBUG)