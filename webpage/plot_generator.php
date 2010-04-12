<html xmlns="http://www.w3.org/1999/xhtml">
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
		<title>Happy Face Plot Generator</title>
	</head>
	<body>
		<h2><strong>Module: <?php echo $_GET["module"]?></strong></h2>
		<form action="<?php echo $PHP_SELF; ?>" method="get">

<?php
$timestamp_var = 'timestamp';
if(isset($_GET['timestamp_var']))
	$timestamp_var = $_GET['timestamp_var'];
?>

			<input type="hidden" name="module" value="<?php echo htmlentities($_GET["module"]); ?>" />
			<input type="hidden" name="subtable" value="<?php echo htmlentities($_GET["subtable"]); ?>" />
			<input type="hidden" name="variables" value="<?php echo htmlentities($_GET["variables"]); ?>" />
			<input type="hidden" name="timestamp_var" value="<?php echo htmlentities($timestamp_var); ?>" />
			<input type="hidden" name="constraint" value="<?php echo htmlentities($_GET['constraint']); ?>" />
			<input type="hidden" name="squash" value="<?php echo htmlentities($_GET['squash']); ?>" />

			<table>
				<tr>
					<td>
						Start:
					</td>
					<td>
						<input name="date0" type="text" size="10" style="text-align:center;" value="<?php echo $_GET["date0"]?>" />
						<input name="time0" type="text" size="5" style="text-align:center;" value="<?php echo $_GET["time0"]?>" />
					</td>
					<td>
						End:
					</td>
					<td>
						<input name="date1" type="text" size="10" style="text-align:center;" value="<?php echo $_GET["date1"]?>" />
						<input name="time1" type="text" size="5" style="text-align:center;" value="<?php echo $_GET["time1"]?>" />
					</td>
					<td>
						<div><button onfocus="this.blur()">Show Plot</button></div>
					</td>
				</tr>
			</table>

<?php
if(isset($_GET['squash']) && intval($_GET['squash']) != 0)
  $variables = array($_GET['variables']);
else
  $variables = explode(',', $_GET['variables']);

foreach($variables as $variable)
{
?>
			<h3>Variable(s): <?php echo htmlentities($variable); ?></h3>
			<p><img alt="" border="2" src="show_plot.php?module=<?php echo htmlentities($_GET["module"]); ?>&subtable=<?php echo htmlentities($_GET["subtable"]); ?>&variables=<?php echo htmlentities($variable); ?>&date0=<?php echo htmlentities($_GET["date0"]); ?>&time0=<?php echo htmlentities($_GET["time0"]); ?>&date1=<?php echo htmlentities($_GET["date1"]); ?>&time1=<?php echo htmlentities($_GET["time1"]); ?>&timestamp_var=<?php echo htmlentities($timestamp_var); ?>&constraint=<?php echo htmlentities($_GET['constraint']); ?>" /></p>

<?php

if($variable == "status")
{
	// Show statistics for status
	$dbh = new PDO("sqlite:HappyFace.db");

	$ta0 = date_parse($_GET['date0'] . ' ' . $_GET['time0']);
	$ta1 = date_parse($_GET['date1'] . ' ' . $_GET['time1']);
	$timestamp0 = mktime($ta0['hour'], $ta0['minute'], 0, $ta0['month'], $ta0['day'], $ta0['year']);
	$timestamp1 = mktime($ta1['hour'], $ta1['minute'], 0, $ta1['month'], $ta1['day'], $ta1['year']);

	$module_table = sqlite_escape_string($_GET['module'] . '_table');
	if(isset($_GET['subtable']) && $_GET['subtable'] != '')
		$module_table = sqlite_escape_string($_GET['subtable']);

	$sql_command = "SELECT DISTINCT $timestamp_var,status FROM $module_table WHERE $timestamp_var >= $timestamp0 AND $timestamp_var <= $timestamp1 ORDER BY $timestamp_var";

	$prev_timestamp = -1;
	$prev_status = -1;
	$accum_status = 0.0;
	$accum_timestamp = 0.0;
	$availabality = 0.0;
	foreach($dbh->query($sql_command) as $data)
	{
		$timestamp = $data['timestamp'];
		$status = $data['status'];

		if($prev_timestamp != -1 && $prev_status != -1)
		{
			if($prev_status > 0.5)
				$availability += ($timestamp - $prev_timestamp);

			$accum_status += $prev_status * ($timestamp - $prev_timestamp);
			$accum_timestamp += ($timestamp - $prev_timestamp);
		}

		$prev_timestamp = $timestamp;
		$prev_status = $status;
	}

	// Add period from last timestamp to now
	if($prev_timestamp != -1 && $prev_status != -1)
	{
		$timestamp = time();
		if($prev_status > 0.5)
			$availability += ($timestamp - $prev_timestamp);
		$accum_status += $prev_status * ($timestamp - $prev_timestamp);
		$accum_timestamp += ($timestamp - $prev_timestamp);
	}

	if($accum_timestamp)
	{
		$availability_str = round($availability/$accum_timestamp * 100);
		$mean_str = round($accum_status/$accum_timestamp * 100);
	}
	else
	{
		$availability_str = 'N/A';
		$mean_str = 'N/A';
	}

	echo "Availability (> 0.5): " . $availability_str . "%<br />";
	echo "Status Mean: " . $mean_str . "%<br />";
}?>
			<hr />
<?php
}
?>

		</form>
	</body>
</html>
