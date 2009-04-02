package mod::prod::FaceProduction;

use mod::prod::FaceSAM;
use mod::prod::FaceFairshare;
use mod::prod::FaceDashboard;
use mod::prod::FaceQstat;

#---------------------------------------------------------------------------------

sub collectResults {
	my $self = shift @_;
	my $facevalue = -1;

	my @tests;
	
	$i = 0;
	foreach $key (keys %{$self}) {
		$tests[$i] = $key;
		$i++;
	}

	for ($i = 0; $i < scalar(@tests); $i++) {
		$result_value	= $self->{"$tests[$i]"}->result();
		if ($result_value > $facevalue) { $facevalue = $result_value; }
	}

	return $facevalue;
}

#---------------------------------------------------------------------------------

sub createHTMLFragment {
	my $self = shift @_;
	my @tests;

	open(PROD_HTML, ">../HTMLFragments/PROD_HTML");

	$i = 0;
	foreach $key (keys %{$self}) {
			$tests[$i] = $key;
			$i++;
	}

	for ($i = 0; $i < scalar(@tests); $i++) {
		$self->{$tests[$i]}->createHTMLFragment();

		open($file_handle = $tests[$i], $file = "../HTMLFragments/".$tests[$i]."_HTML");
		while (<$file_handle>) {
			chomp;
			print PROD_HTML "$_\n";
		}
		close($file_handle);
	}

	close(PROD_HTML);

}

#---------------------------------------------------------------------------------

sub new {

	my $self = shift @_;
	my %options = @_;
	my %face = ();
	my @tests;

	$i = 0;
	foreach $key (keys %options) {
		$tests[$i] = $key;
		$i++;
	}

	for ($i = 0; $i < scalar(@tests); $i++) {
		if ( $options{$tests[$i]} ) {
			$module_name = "mod::prod::Face".$tests[$i];
			$face{$tests[$i]} = $module_name->new($options{$tests[$i]});
		}
	}

	my $face = {%face};
	bless $face, $self;
	return $face;
}

1;
