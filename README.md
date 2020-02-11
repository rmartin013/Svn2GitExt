# Svn2GitExt
Did you work in a company so much attached to SVN that it seems they will continue with it until the end of the world?
And cherry on the cake, the projects arborescence is so touchy they use deep nested svn:externals.
This project is my try to perform a slow but sure migration from SVN to GIT in this context.

Svn2GitExt.py is a python script which will automate SVN arborescence cloning into GIT, using git svn to create a bidirectional synchronizing way,
and git subtrees to emulate svn:externals projects into the main project.

$ ./Svn2GitExt.py create -d <working directory> -s <subversion working directory> -b <URL to bitbucket Project> -u <username> -p <password>
=> Create a GIT clone from <subversion working directory> into <working directory>, using main and intermediate repositories hosted on <URL to bitbucket Project> BitBucket project
This command will begin creating a GIT clone from a local Subversion working directory.
- This directory must be up to date with the latest SVN revision, for a simple reason: it will be diffed against the final GIT clone of the main project.
- The <working directory> should not exist, and the basename of its path will be used as the main project name,
and subtree project names derived from svn:externals will be construct on this model <main_project_name>-ext-<external_index>-<external-local-path>.
All GIT repositories (main and subtrees) will be created in the dirname of <working directory>.
- <URL to bitbucket Project> must be the URL to the BitBucket Project where you want to store your incoming GIT repositories.
The REST API 1.0 must be supported by your BitBucket server.

$ ./Svn2GitExt.py purge -b <URL to bitbucket Project> -u <username> -p <password>
=> Deleted all repositories from a specifid Bitbucket project accessible from <URL to bitbucket Project> with a browser, using credentials <username>/<password>
