# -*- coding: utf-8 -*-

import cherrypy as cp
import hf, datetime, time, logging, traceback, os, subprocess
from hf.module.database import hf_runs
import hf.plotgenerator
from sqlalchemy import *
from mako.template import Template

class CategoryDispatcher(object):
    """
    Show a page for displaying the contents of a category.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__module__)
        self.category_list = hf.category.createCategoryObjects()
        if hf.config.get('plotgenerator', 'enabled').lower() == 'true':
            hf.plotgenerator.init()
            try:
                filename = os.path.join(hf.hf_dir, hf.config.get("paths", "hf_template_dir"), "plot_timeseries.html")
                cp.engine.autoreload.files.add(filename)
                self.timeseries_template = Template(filename=filename, lookup=hf.template_lookup)
            except Exception:
                self.logger.error("Cannot initialize timeseries template")
                self.logger.debug(traceback.format_exc())
    
    @cp.expose
    def plot(self, plt_type=None, img=None, **kwargs):
        if hf.config.get('plotgenerator', 'enabled').lower() != 'true':
            return "Plot Generator disabled by HappyFace configuration"
        
        if img == "img":
            if plt_type == "time":
                return hf.plotgenerator.timeseriesPlot(**kwargs)
        else:
            # just get the lastest run, we don't really need it
            run = hf_runs.select(hf_runs.c.time).order_by(hf_runs.c.time.asc()).execute().fetchone()
            category_dict = dict((cat.name, cat.getCategory(run)) for cat in self.category_list)
            template_context = {
                    "static_url": hf.config.get('paths', 'static_url'),
                    "happyface_url": hf.config.get('paths', 'happyface_url'),
                    "category_list": category_dict.values(),
                    "module_list": [],
                    "hf": hf,
                }
            for cat in category_dict.itervalues():
                template_context["module_list"].extend(cat.module_list)
            if plt_type == "time":
                return self.timeseries_template.render(**template_context)
        
        # if we get here, 404!
        return "404" # TODO 404!
        
    @cp.expose
    def default(self, category=None, **kwargs):
        self.logger.warning(category)
        try:
            '''
            Select a hf run based on the passed 'date' and 'time' parameters. If not
            specified, use most recent run. If they are specified, make sure they do
            not mark a point in the future.
            Because (usually) microseconds are stored in the database, too, we have
            to pad with extra 59 seconds (note: 59 because it will be the same minute
            but there will only be a single "dead" second, we can live with that).
            '''
            self.logger.debug(kwargs['date'] if 'date' in kwargs is not None else '')
            self.logger.debug(kwargs['time'] if 'time' in kwargs is not None else '')
            
            time_error_message = ''
            
            time_obj = datetime.datetime.fromtimestamp(int(time.time()))
            try:
                timestamp = kwargs['date'] if 'date' in kwargs is not None else time_obj.strftime('%Y-%m-%d')
                timestamp += '_' + (kwargs['time'] if 'time' in kwargs else time_obj.strftime('%H:%M'))
                # notice the extra seconds to avoid microsecond and minute issues
                time_obj = datetime.datetime.fromtimestamp(time.mktime(time.strptime(timestamp, "%Y-%m-%d_%H:%M"))+59)

            except Exception:
                time_error_message = "The passed time was invalid"
            
            if time_obj > datetime.datetime.fromtimestamp(int(time.time())+59):
                time_error_message = "HappyFace is not an oracle"
                time_obj = datetime.datetime.fromtimestamp(int(time.time())+59)
                
            run = hf_runs.select(hf_runs.c.time <= time_obj).order_by(hf_runs.c.time.desc()).execute().fetchone()
            if run is None:
                time_error_message = "No data so far in past"
                run = hf_runs.select(hf_runs.c.time >= time_obj).order_by(hf_runs.c.time.asc()).execute().fetchone()
                time_obj = run["time"]
            run = {"id":run["id"], "time":run["time"]}
            
            category_dict = dict((cat.name, cat.getCategory(run)) for cat in self.category_list)
            
            selected_category = None
            for c in category_dict.itervalues():
                if c.name == category:
                    selected_category = c
                    break
            
            try:
                svn_rev = subprocess.Popen(['svnversion'], 0, None, None, subprocess.PIPE).stdout.read().strip()
            except Exception:
                svn_rev = 'exported'
            
            template_context = {
                "static_url": hf.config.get('paths', 'static_url'),
                "happyface_url": hf.config.get('paths', 'happyface_url'),
                "category_list": category_dict.values(),
                "module_list": [],
                "hf": hf,
                "time_specified": ('date' in kwargs or 'time' in kwargs),
                "date_string": time_obj.strftime('%Y-%m-%d'),
                "time_string": time_obj.strftime('%H:%M'),
                "histo_step": kwargs['s'] if 's' in kwargs else "00:15",
                "run": run,
                'selected_module': None,
                'selected_category': selected_category,
                'time_error_message': time_error_message,
                'svn_rev': svn_rev,
            }

            for cat in category_dict.itervalues():
                template_context["module_list"].extend(cat.module_list)
            
            doc = u""
            
            if 'action' in kwargs:
                if kwargs['action'].lower() == 'getxml':
                    doc = hf.category.renderXmlOverview(run, template_context)
                else:
                    doc = u'''<h2>Unkown action</h2>
                    <p>The specified action <em>%s</em> is not known.<p>''' % kwargs['action']
            else:
                '''
                Show the requested category or a 'blank' overview if
                no category is specified.
                '''
                if category is None:
                    filename = os.path.join(hf.hf_dir, hf.config.get("paths", "hf_template_dir"), "index.html")
                    index_template = Template(filename=filename, lookup=hf.template_lookup)
                    doc = index_template.render(**template_context)
                elif category is not None and not category in category_dict:
                    raise cp.HTTPError(404, u"<h2>404 – File Not Found</h2>")
                elif category is not None:
                    if run is not None:
                        doc = category_dict[category].render(template_context)
                    else:
                        doc = u"<h2>No data found at this time</h2>"
            return doc
        except Exception, e:
            self.logger.error("Page request threw exception: %s" % str(e))
            self.logger.debug(traceback.format_exc())
            raise cp.HTTPError(500, "HappyFace threw an exception, see logfile for detailed info")
