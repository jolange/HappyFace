import os, sys

from CMSPhedexAgents import *

class cms_phedex_agents_debug(CMSPhedexAgents):

    def __init__(self,category,timestamp,archive_dir):

        CMSPhedexAgents.__init__(self,category,timestamp,archive_dir)
