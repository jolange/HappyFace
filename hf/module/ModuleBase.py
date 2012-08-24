import hf
from hf.module.module import __module_class_list as _module_class_list
from hf.module.module import __column_file_list as _column_file_list
from mako.template import Template
import cherrypy as cp
import logging, traceback, os, re
from sqlalchemy import Integer, Float, Numeric, Table, Column, Sequence, Text, Integer, Float, ForeignKey

class ModuleMeta(type):
    def __init__(self, name, bases, dct):
        if name == "ModuleBase":
            super(ModuleMeta, self).__init__(name, bases, dct)
            return
            
        if "config_keys" not in dct:
            raise hf.exceptions.ModuleProgrammingError(name, "No config_keys dictionary specified")
        if "config_hint" not in dct:
            #raise hf.exceptions.ModuleProgrammingError(name, "No configuration hint config_hint specified (empty string possible)")
            self.config_hint = ''
        if "table_columns" not in dct:
            raise hf.exceptions.ModuleProgrammingError(name, "table_colums not specified")
        if "subtable_columns" not in dct:
            self.subtable_columns = {}
        
        super(ModuleMeta, self).__init__(name, bases, dct)
        
        self.addModuleClass(name)
        
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        tabname = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        
        try:
            tab = self.generateModuleTable(tabname, self.table_columns[0])
            for fc in self.table_columns[1]:
                self.addColumnFileReference(tab, fc)
        except Exception, e:
            raise hf.exceptions.ModuleProgrammingError(name, "Generating module table failed: " + str(e))
        for sub, (columns, fc_list) in self.subtable_columns.iteritems():
            try:
                tab = self.generateModuleSubtable(sub, columns)
                for fc in fc_list:
                    self.addColumnFileReference(tab, fc)
            except Exception, e:
                raise hf.exceptions.ModuleProgrammingError(name, "Generating subtable %s failed: %s" % (sub, str(e)))
        
        del self.table_columns
        try:
            del self.subtable_columns
        except Exception:
            pass
        
    def generateModuleTable(self, tabname, columns):
        table = Table("mod_"+tabname, hf.database.metadata,
            *([
                Column('id', Integer, Sequence("mod_"+tabname+'_id_seq'), primary_key=True),
                Column('instance', Text, ForeignKey("module_instances.instance")),
                Column('run_id', Integer, ForeignKey("hf_runs.id")),
                Column('status', Float),
                Column('description', Text),
                Column('instruction', Text),
                Column('error_string', Text),
                Column('source_url', Text),
            ] + columns))
        self.module_table = table
        self.subtables = {}
        table.module_class = self
        return table
        
    def generateModuleSubtable(self, name, columns):
        tabname = "sub_"+self.module_table.name[4:] + '_' + name
        table = Table(tabname,
            hf.database.metadata,
            *([
                Column('id', Integer, Sequence(tabname+'_id_seq'), primary_key=True),
                Column('parent_id', Integer, ForeignKey(self.module_table.c.id)),
            ] + columns))
        self.subtables[name] = table
        table.module_class = self
        return table

    def addModuleClass(self, name):
        if name in _module_class_list:
            raise hf.exception.ConfigError('A module with the name %s was already imported!' % name)
        self.module_name = name
        _module_class_list[name] = self
        
    def addColumnFileReference(self, table, column):
        name = table.name if isinstance(table, Table) else table
        _column_file_list[name] = _column_file_list[name]+[column] if name in _column_file_list else [column]

class ModuleBase:
    """
    Base class for HappyFace modules.
    A module provides two core functions:
    1) Acquisition of data through the methods
      1] prepareAcquisition: Specify the files to download
      2] extractData: Return a dictionary with data to fill into the database
      3] fillSubtables: to write the datasets for the modules subtables
    2) Rendering the module by returning a template data dictionary
     in method getTemplateData.
    
    Because thread-safety is required for concurrent rendering, the module itself
    MUST NOT save its state during rendering. The modules functions are internally
    accessed by the ModuleProxy class.
    
    The status of the module represents a quick overview over the current module
    status and fitness.
    * 0.66 <= status <= 1.0  The module is happy/normal operation
    * 0.33 <= status < 0.66  Neutral, there are things going wrong slightly.
    * 0.0  <= status < 0.33  Unhappy, something is very wrong with the monitored modules
    * status = -1            An error occured during module execution
    * status = -2            Data could not be retrieved (download failed etc.)
    
    The category status is calculated with a user specified algorithm from the statuses
    of the modules in the category. If there is missing data or an error, the category
    index icon is changed, too.
    
    In practice, there is no "visual" difference between status -1 and -2, but there might
    be in future.
    """
    
    __metaclass__ = ModuleMeta
    
    config_defaults = {
        'description': '',
        'instruction': '',
        'type': 'rated',
        'weight': '1.0',
    }
    
    # set by hf.module.importModuleClasses and
    # hf.module.addModuleClass when the module is imported
    table = None
    subtables = None
    filepath = None
    
    def __init__(self, instance_name, config, run, dataset, template):
        self.logger = logging.getLogger(self.__module__+'('+instance_name+')')
        self.module_name = self.__class__.module_name
        self.module_table = self.__class__.module_table
        self.subtables = self.__class__.subtables
        self.instance_name = instance_name
        self.config = config
        self.run = run
        self.dataset = dataset
        self.template = template
        self.category = None # set by CategoryProxy.getCategroy() after creating specific module instances
        
        if not "type" in self.config:
            self.type = "unrated"
            self.logger.warn("Module type not specified, using 'unrated'")
        else:
            self.type = self.config['type']
        if self.type not in ('rated', 'plots', 'unrated'):
            self.logger.warn("Unknown module type '%s', using 'unrated'" % self.type)
            self.type = "unrated"
            
        if not "weight" in self.config:
            self.weight = 0.0
            self.logger.warn("Module weight not specified, ignore in calculations")
        else:
            try:
                self.weight = float(self.config['weight'])
            except Exception:
                self.logger.warn("Module weight not numeric, using 0.0")
    
    def prepareAcquisition(self):
        pass
    
    def fillSubtables(self, module_entry_id):
        pass
    
    def getTemplateData(self):
        """
        Override this method if your template requires special
        preprocessing of data or you have data in subtables.
        """
        return {"dataset": self.dataset, "run": self.run}
        
    def __unicode__(self):
        return self.instance_name
    
    def __str__(self):
        return self.instance_name
    
    def getStatusString(self):
        if self.isUnauthorized():
            return 'noinfo' if self.type == 'rated' else 'unavail_plot'
        icon = 'unhappy'
        if self.dataset is None:
            icon = 'unhappy' if self.type == 'rated' else 'unavail_plot'
        else:
            if self.type == 'rated':
                if self.dataset['status'] > 0.66:
                    icon = 'happy'
                elif self.dataset['status'] > 0.33:
                    icon = 'neutral'
                else:
                    icon = 'unhappy'
            else:
                icon = 'avail_plot' if self.dataset['status'] > 0.9 else 'unavail_plot'
        return icon
    
    def url(self, only_anchor=True, time=None):
        # something along ?date=2012-03-24&amp;time=17:20&amp;t=batchsys&amp;m=${module.instance_name}
        return ('' if only_anchor else self.category.url(time=time)) + u"#" + self.instance_name
        
    def getStatusIcon(self):
        return os.path.join(hf.config.get('paths', 'template_icons_url'), 'mod_'+self.getStatusString()+'.png')
    
    def getNavStatusIcon(self):
        return os.path.join(hf.config.get('paths', 'template_icons_url'), 'nav_'+self.getStatusString()+'.png')
        
    def getPlotableColumns(self):
        blacklist = ['id', 'run_id', 'instance', 'description', 'instruction', 'error_string', 'source_url']
        types = [Integer, Float, Numeric]
        def isnumeric(cls):
            for t in types:
                if isinstance(cls,t):
                    return True
            return False
        numerical_cols = filter(lambda x: isnumeric(x.type), self.module_table.columns)
        return [col.name for col in numerical_cols if col.name not in blacklist]
    
    def isAccessRestricted(self):
        return self.config['access'] != 'open'
    
    def isUnauthorized(self):
        return self.config['access'] == 'restricted' and not cp.request.cert_authorized
        
    def getPlotableColumnsWithSubtables(self):
        cols = {'': self.getPlotableColumns()}
        
        blacklist = ['id', 'parent_id']
        types = [Integer, Float, Numeric]
        def isnumeric(cls):
            for t in types:
                if isinstance(cls,t):
                    return True
            return False
        
        for name, table in self.subtables.iteritems():
            numerical_cols = filter(lambda x: isnumeric(x.type), table.columns)
            cols[name] = [col.name for col in numerical_cols if col.name not in blacklist]
        
        return cols
        
    def getAllColumnsWithSubtables(self):
        blacklist = ['id', 'instance', 'description', 'instruction', 'error_string', 'source_url']
        blacklist_sub = ['id', 'parent_id']
        cols = {'': [col.name for col in self.module_table.columns if col.name not in blacklist]}
        for name, table in self.subtables.iteritems():
            cols[name] = [col.name for col in table.columns if col.name not in blacklist_sub]
        
        return cols
    def render(self):
        module_html = ''
        if self.template is None:
            return '<p class="error">Rendering module %s failed because template was not loaded</p>' % self.instance_name
        if self.isUnauthorized():
            return '<p class="error">Access to Module %s is restricted, please log in with your certificate.</p>' % self.instance_name
        try:
            template_data = {
                'module': self,
                'data_stale': self.run['stale'],
                'run': self.run,
                'hf': hf
            }
            if self.dataset is None:
                template_data['no_data'] = True
                module_html = self.template.render(**template_data)
            else:
                template_data.update(self.getTemplateData())
                template_data['no_data'] = False
                module_html = self.template.render(**template_data)
        except Exception, e:
            module_html = "<p class='error'>Final rendering of '%s' failed completely!</p>" % self.instance_name
            self.logger.error("Rendering of module %s failed: %s" %(self.module_name, str(e)))
            self.logger.debug(traceback.format_exc())
        return module_html
        