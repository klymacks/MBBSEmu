Configuring Logon Automation for the Paradigm Server
================================================================================
On a typical server, each character would have its own BBS entry with a unique
username and password. Other characters on the same BBS would use the same
overall BBS configuration, but with different values entered in the username and
password fields.

The Paradigm server works differently.

Paradigm uses one account for all characters. After logging into the account,
you select the realm and then choose which character slot to play. Because of
this, we need to adapt the client's configuration slightly.

In MegaMud, the username field is called "User ID". For Paradigm, the
User ID field should not contain your actual account login name. Instead, the
User ID field should contain the character slot number you want that "BBS" entry
to use.

For example, if the character you want to play is listed as character 2 on the
Paradigm character selection screen, enter 2 in the User ID field.

The password field should contain the password for your shared Paradigm account.


BBS / Realm Entries
===================
The pre-configured BBS entries are actually Paradigm realms:

Paradigm Game 1 PVE
Paradigm Game 2 PVP
Paradigm Game 3
Paradigm Game 4
Paradigm TEST PVE
Paradigm TEST PVP

Each BBS entry already has its realm number pre-filled in the logon automation.
You do not need to change the realm number.


Shared Account Name
===================
Your shared Paradigm account name must be entered in the logon automation for
each realm/BBS entry you use.  For each realm/BBS entry:

1. Select the realm.
2. Click Edit.
3. Under Logon Automation, select the entry for: "Please enter your username"
4. In the Reply field, enter your shared account name followed by ^M.
   Example: YourSharedUsername^M
5. Click OK.
6. Repeat for each realm/BBS entry you plan to use.


Character Settings
==================
For each character entry:

User ID:   character slot number
Password:  shared Paradigm account password

Do not put your shared account username in the User ID field.

The User ID field is used later during automation as {userid}, which selects the
character slot from the character selection menu.


Automation Reference
====================
The automation should look similar to this:

Please enter your username or "new":/YourSharedUsername^M
Please enter your password:/{pswd}^M
P : Paradigm/P^M
{ Realm Selection }/pre-filled realm number^M
{ Character Selection }/{userid}^M

Only the shared username usually needs to be changed.

{pswd} comes from the Password field.
{userid} (character slot number) comes from the User ID field.


Summary
=======
BBS entry   = Paradigm realm
User ID     = character slot number
Password    = shared Paradigm account password
Username    = entered in logon automation for each realm


TLDR Setup
==========
1. Open BBS settings
2. Configure your shared server account name--
	a. Pick the Paradigm realm/BBS entry you want to use
	b. Click Edit
	c. Under Logon Automation, select: "Please enter your username"
	d. In the Reply field, enter your shared Paradigm account name followed by ^M
		ex: YourSharedUsername^M
	e. Click OK
	f. Repeat for each realm/BBS entry you plan to use
3. Set User ID: character slot number for selected realm
4. Set Password: your shared Paradigm account password
