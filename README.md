# GOG.com backup
Backup all your gog.com content.

Script to create a complete backup of your gog.com account.

You have to enter your login, password and manually press the "log in" button when the browser opens the authorization window.

Please note that this script makes complete backup of all downlodable content belonging to your account. This includes all available versions of all games you have. For all OSes and all languages. The resulting file set might be surprisingly large. E.g. my backup is just over 73 GB for 52 games I have in my account.

TODO: 
	1) add generation of a simple index.html
	2) Implement proper checks for game updates
	3) Implement support for DLCs (can plase somebody do this as I do not own any DLC-enabled games, can't test)
	4) Tidy up the source
	5) Unittests?

Reqires: selenium & Firefox
