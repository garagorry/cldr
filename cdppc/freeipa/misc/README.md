# FreeIPA Status
Simple Ways For Getting Things Done

<h1>Disclaimer for garagorry.com | github.com/garagorry </h1>

<p>If you require any more information or have any questions about our site's disclaimer, please feel free to contact us by email at jimmy@garagorry.com.</p>

<h2>Disclaimers for garagorry.com</h2>

<p>All the information on this website - https://garagorry.com | https://github.com/garagorry - is published in good faith and for general information purpose only. garagorry.com does not make any warranties about the completeness, reliability and accuracy of this information. Any action you take upon the information you find on this website (garagorry.com | github.com/garagorry), is strictly at your own risk. garagorry.com will not be liable for any losses and/or damages in connection with the use of 
our website.</p>

<p>From our website, you can visit other websites by following hyperlinks to such external sites. While we strive to provide only quality links to useful and ethical websites, we have no control over the content and nature of these sites. These links to other websites do not imply a recommendation for all the content found on these sites. Site owners and content may change without notice and may occur before we have the opportunity to remove a link which may have gone 'bad'.</p>

<p>Please be also aware that when you leave our website, other sites may have different privacy policies and terms which are beyond our control. Please be sure to check 
the Privacy Policies of these sites as well as their "Terms of Service" before engaging in any business or uploading any information.</p>

<h2>Consent</h2>

<p>By using our website, you hereby consent to our disclaimer and agree to its terms.</p>

<h2>Update</h2>

<p>Should we update, amend or make any changes to this document, those changes will be prominently posted here.</p>

<h2>Get FreeIPA Status</h2>

<p>freeipa_status_functions.sh is a file with basic health checks that can be executed from one of the FreeIPA nodes as the root user.</p>

<h3>How to use it</h3>

 1) Copy freeipa_status_functions.sh to ~/.freeipa_status_functions.sh 
 2) Add the following lines to your ~/.bashrc profile file:
    source ~/.freeipa_status_functions.sh
 3) Reload the Profile file using:
    source ~/.bashrc
 4) List the available functions using:
    awk '/^function/ {print $2}' ~/.freeipa_status_functions.sh
 5) Execute a test by using the function name, for example:
    freeipa_cipa_state
