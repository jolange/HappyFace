from ModuleBase import *
#from HTMLParsing import *
import time, re, HTMLParser

class dCacheMoverInfo(ModuleBase):

    def __init__(self,module_options):
        ModuleBase.__init__(self,module_options)
        
        self.db_keys['job_info_database'] = StringCol()
        self.db_values['job_info_database'] = ''
        
        self.watch_jobs = self.configService.get('setup', 'watch_jobs').split(',')
        
        self.critical_queue_threshold = self.configService.get('setup', 'critical_queue_threshold')
        self.db_keys['critical_queue_threshold'] = StringCol()
        self.db_values['critical_queue_threshold'] = self.configService.get('setup', 'critical_queue_threshold')


    def process(self):
        
        self.job_info_database = self.__module__ + '_job_info_database'
        self.db_values['job_info_database'] = self.job_info_database
        job_info_db_keys = {}
        job_info_db_keys['pool'] = StringCol()
        job_info_db_keys['domain'] = StringCol()
        job_info_db_keys['job'] = StringCol()
        job_info_db_keys['active'] = IntCol()
        job_info_db_keys['max'] = IntCol()
        job_info_db_keys['queued'] = IntCol()
        
        job_info_table = self.table_init(self.job_info_database, job_info_db_keys)
        
        class TableRowExtractor(HTMLParser.HTMLParser):
            '''
            Parse the HTML and extract all rows from the table.
            The format is a list of rows, each row is a list with format [th?, class, data],
            saved in the extractedRows attribute
            '''
            extractedRows = []
            __currentRow = []
            __curTag = ''
            def handle_starttag(self, tag, attr):
                self.__curTag = tag
                if tag == "tr":
                    self.__currentRow = []
                elif tag == 'td' or tag == 'th':
                    cssClass = ''
                    for a in attr:
                        if a[0] == 'class': cssClass = a[1]
                    self.__currentRow.append([tag == 'th', cssClass, ''])
                    
            def handle_endtag(self, tag):
                    if tag == "tr":
                        self.extractedRows.append(self.__currentRow)
                        self.__currentRow = []
                        
            def handle_data(self, data):
                if data == '\n' or data == '\r\n' or data == '':
                    return
                if self.__curTag == 'td' or self.__curTag == 'th':
                    self.__currentRow[len(self.__currentRow)-1][2] = data

        def extractPools(rows):
            '''
            This applies 'filters' to the row-data to discard headlines, totals
            and extract only pools that are interessting for us.
            
            Return value is a dictionary of pools, key is pool name, value
            is a tuple (domain, value-dict). Value-dict contains the data, key
            is the transfer-type, value is a tripple (cur, max, queue)
            '''
            protocols = []
            # extract all protocols (they are in the first row, starting at third column
            for p in rows[0][2:]:
                protocols.append(p[2])
            
            pools = {}
            for r in rows:
                # Discard empty rows
                if len(r) == 0: continue
                # Discard all rows starting with a head
                if r[0][0]: continue
                
                # We now    have data-rows only.
                name, domain = r[0][2], r[1][2]
                
                # Only CMS read-tape pools
                if not re.search(r'rT_cms$', name):
                    #print 'Discard', name
                    continue
                values = {}
                for i,proto in enumerate(protocols):
                    values[proto] = (int(r[i*3+2][2]), int(r[i*3+3][2]), int(r[i*3+4][2]))
                    
                pools[name] = (domain, values)
            return pools

        # now actually import the data
        job_info_db_value_list = []

        success,sourceFile = self.downloadService.getFile(self.getDownloadRequest('queue_info_html'))
        tableRowExtractor = TableRowExtractor()
        for line in open(sourceFile, 'r'):
            tableRowExtractor.feed(line)
        pool_list = extractPools(tableRowExtractor.extractedRows)
        
        num_queuing_pools = 0
        has_critical_queue = False
        
        for pool,value in pool_list.iteritems():
            job_has_queue = False
            # Add all the job-values that interesst us to database as a new row per job
            for job in self.watch_jobs:
                job_info_db_values = {}
                job_info_db_values['pool'] = pool
                job_info_db_values['domain'] = value[0]
                job_info_db_values['job'] = job
                job_info_db_values['active'] = int(value[1][job][0])
                job_info_db_values['max'] = int(value[1][job][1])
                job_info_db_values['queued'] = int(value[1][job][2])
                job_info_db_value_list.append(job_info_db_values)

                if int(value[1][job][2]) > 0:
                    job_has_queue = True
                elif int(value[1][job][2]) > self.critical_queue_threshold:
                    has_critical_queue = True
            if job_has_queue:
                num_queuing_pools += 1
        # calculate happiness as ratio of queued pools to total pools,
        # be sad if there is a critical queue
        self.status = 1.0 - float(num_queuing_pools) / len(pool_list)
        if has_critical_queue: self.status = 0.0
        
                
        self.table_fill_many(job_info_table, job_info_db_value_list)
        self.subtable_clear(job_info_table, [], self.holdback_time)



    def output(self):
        
        js = []
        js.append('<script type="text/javascript">')
        js.append('function ' + self.__module__ + '_plot_button(pool, job)')
        js.append('{')
        js.append('  document.getElementById("' + self.__module__ + '_constraint").value = "job=" + job + ";pool=" + pool;')
        js.append('  document.getElementById("' + self.__module__ + '_extra_title").value = "Pool: " + pool + ",  Job: " + job;')
        js.append('}')
        js.append('</script>')

        mc_overview_begin = []
        mc_overview_begin.append('<table class="TableData">')
        mc_overview_begin.append(' <tr class="TableHeader">')
        mc_overview_begin.append('  <th>Job</th>')
        mc_overview_begin.append('  <th>Active</th>')
        mc_overview_begin.append('  <th>Max</th>')
        mc_overview_begin.append('  <th>Queued</th>')
        mc_overview_begin.append(' </tr>')
        
        mc_overview_row = []
        mc_overview_row.append(" <tr class=\"'.$jobStatus.'\">")
        mc_overview_row.append("  <td>'.$job['job'].'</td>")
        mc_overview_row.append("  <td>'.$job['a'].'</td>")
        mc_overview_row.append("  <td>'.$job['m'].'</td>")
        mc_overview_row.append("  <td>'.$job['q'].'</td>")
        mc_overview_row.append(' </tr>')
        
        mc_overview_end = []
        mc_overview_end.append('</table>')
        mc_overview_end.append('<br />')
        
        mc_detailed_begin = []
        mc_detailed_begin.append("""<input type="button" value="show/hide details" onfocus="this.blur()" onclick="show_hide(\\\'""" + self.__module__+ """_detailed\\\');" />""")
        mc_detailed_begin.append('<form method="get" action="plot_generator.php" onsubmit="javascript:submitFormToWindow(this);">')
        mc_detailed_begin.append('<div class="DetailedInfo" id="' + self.__module__+ '_detailed" style="display:none;">')
        mc_detailed_begin.append(  ' <table style="font: bold 0.7em sans-serif; width:800px; background-color: #ddd; border: 1px #999 solid;">')
        mc_detailed_begin.append(  '  <tr>')
        mc_detailed_begin.append(  '   <td>Start:</td>')
        mc_detailed_begin.append(  '   <td>')
        mc_detailed_begin.append("""    <input name="date0" type="text" size="10" style="text-align:center;" value="' . strftime("%Y-%m-%d", strtotime("$date_string $time_string") - 48*60*60) . '" />""")
        mc_detailed_begin.append("""    <input name="time0" type="text" size="5" style="text-align:center;" value="' . strftime("%H:%M", strtotime("$date_string $time_string") - 48*60*60) . '" />""")
        mc_detailed_begin.append(  '   </td>')
        mc_detailed_begin.append(  '   <td>End:</td>')
        mc_detailed_begin.append(  '   <td>')
        mc_detailed_begin.append("""    <input name="date1" type="text" size="10" style="text-align:center;" value="' . $date_string . '" />""")
        mc_detailed_begin.append("""    <input name="time1" type="text" size="5" style="text-align:center;" value="' . $time_string . '" />""")
        mc_detailed_begin.append(  '   </td>')
        mc_detailed_begin.append(  '   <td align="right">')
        mc_detailed_begin.append(  '    <input type="checkbox" name="renormalize" value="1" style="vertical-align: middle; margin: 0px;" />&nbsp;Show Trend plot')
        mc_detailed_begin.append(  '    <input type="hidden" name="module" value="'+ self.__module__ + '" />')
        mc_detailed_begin.append(  '    <input type="hidden" name="subtable" value="' + self.job_info_database + '" />')
        mc_detailed_begin.append(  '    <input type="hidden" name="variables" value="active,max,queued" />')
        mc_detailed_begin.append(  '    <input type="hidden" name="squash" value="1" />')
        mc_detailed_begin.append(  '    <input type="hidden" name="legend" value="right" />')
        mc_detailed_begin.append(  '    <input type="hidden" id="'+self.__module__ + '_constraint' + '" name="constraint" value="" />')
        mc_detailed_begin.append(  '    <input type="hidden" id="'+self.__module__ + '_extra_title' + '" name="extra_title" value="" />')
        mc_detailed_begin.append(  '   </td>')
        mc_detailed_begin.append(  '  </tr>')
        mc_detailed_begin.append(  ' </table>')
        mc_detailed_begin.append(' <table class="TableData" id="' + self.__module__ + '_details_table">')
        mc_detailed_begin.append('  <tr class="TableHeader">')
        mc_detailed_begin.append('   <th>Pool</th>')
        mc_detailed_begin.append('   <th>Job</th>')
        mc_detailed_begin.append('   <th>Active</th>')
        mc_detailed_begin.append('   <th>Max</th>')
        mc_detailed_begin.append('   <th>Queued</th>')
        mc_detailed_begin.append('   <th>Plot Jobs</th>')
        mc_detailed_begin.append('  </tr>')

        mc_detailed_head_row = []
        mc_detailed_head_row.append(" <tr class=\"'.$jobStatus.'\">")
        mc_detailed_head_row.append("  <td rowspan=\"'.$numJobs.'\" class=\"'.$poolStatus.'\">'.$detail['pool'].'</td>")
        mc_detailed_head_row.append("  <td>'.$detail['job'].'</td>")
        mc_detailed_head_row.append("  <td>'.$detail['active'].'</td>")
        mc_detailed_head_row.append("  <td>'.$detail['max'].'</td>")
        mc_detailed_head_row.append("  <td>'.$detail['queued'].'</td>")
        mc_detailed_head_row.append("  <td><button onfocus=\"this.blur()\" onclick=\"" + self.__module__ + "_plot_button(\\''.$detail['pool'].'\\', \\''.$detail['job'].'\\')\">Plot</button></td>")
        mc_detailed_head_row.append(' </tr>')
        mc_detailed_row = []
        mc_detailed_row.append(" <tr class=\"'.$jobStatus.'\">")
        mc_detailed_row.append("  <td>'.$detail['job'].'</td>")
        mc_detailed_row.append("  <td>'.$detail['active'].'</td>")
        mc_detailed_row.append("  <td>'.$detail['max'].'</td>")
        mc_detailed_row.append("  <td>'.$detail['queued'].'</td>")
        mc_detailed_row.append("  <td><button onfocus=\"this.blur()\" onclick=\"" + self.__module__ + "_plot_button(\\''.$detail['pool'].'\\', \\''.$detail['job'].'\\')\">Plot</button></td>")
        mc_detailed_row.append(' </tr>')
        
        
        mc_detailed_end = []
        mc_detailed_end.append('</table>')
        mc_detailed_end.append('</form>')

        module_content = """<?php
        
        print('""" + self.PHPArrayToString(js) + """');
        
        $overview_sqlquery = "SELECT job, sum(`active`) as a, sum(`max`) as m, sum(`queued`) as q FROM " . $data["job_info_database"] . " WHERE timestamp = " . $data["timestamp"] . " GROUP BY job";
        $detailed_sqlquery = "SELECT db.pool, db.job, db.active, db.`max`, db.queued, sub.pool_queue
                FROM " . $data["job_info_database"] . " db
                INNER JOIN
                (
                    SELECT pool, sum(queued) as pool_queue FROM " . $data["job_info_database"] . " WHERE timestamp = " . $data["timestamp"] . " GROUP BY pool
                ) sub
                ON db.pool = sub.pool WHERE db.timestamp = " . $data["timestamp"] . " ORDER BY db.pool,db.job";
        
        $groups = array();
        print('""" + self.PHPArrayToString(mc_overview_begin) + """');
        $numJobs = 0; // ugly but works
        foreach ($dbh->query($overview_sqlquery) as $job)
        {
            $jobStatus = 'ok';
            if($job['q'] >= $data['critical_queue_threshold'])
                $jobStatus = 'critical';
            elseif($job['q'] > 0)
                $jobStatus = 'warning';
            print('""" + self.PHPArrayToString(mc_overview_row) + """');
            $numJobs += 1;
        }
        print('""" + self.PHPArrayToString(mc_overview_end) + """');


        print('""" + self.PHPArrayToString(mc_detailed_begin) + """');
        $prevPool = ''; // required for rowspan
        foreach ($dbh->query($detailed_sqlquery) as $detail)
        {
            $jobStatus = 'ok';
            if($detail['queued'] >= $data['critical_queue_threshold'])
                $jobStatus = 'critical';
            elseif($detail['queued'] > 0)
                $jobStatus = 'warning';
            if($prevPool == $detail['pool'])
            
                print('""" + self.PHPArrayToString(mc_detailed_row) + """'); 
            else
            {
                $poolStatus = 'ok';
                if($detail['pool_queue'] >= $data['critical_queue_threshold'])
                    $poolStatus = 'critical';
                elseif($detail['pool_queue'] > 0)
                    $poolStatus = 'warning';
                print('""" + self.PHPArrayToString(mc_detailed_head_row) + """'); 
                $prevPool = $detail['pool'];
            }
        }
        print('""" + self.PHPArrayToString(mc_detailed_end) + """');

        ?>"""
        return self.PHPOutput(module_content)
