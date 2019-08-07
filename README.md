# Svn2GitExt
Did you work in a company so much attached to SVN that it seems they will continue with it until the end of the world?
And cherry on the cake, the projects arborescence is so touchy they use deep nested svn:externals. 
This project is my try to perform a slow but sure migration from SVN to GIT in this context. 

Svn2GitExt.py is a python script which will automate SVN arborescence cloning into GIT, using git svn to create a bidirectional synchronizing way, and git subtrees to emulate svn:externals projects into the main project.
