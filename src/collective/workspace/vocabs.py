from Acquisition import aq_chain
from collective.workspace.interfaces import IWorkspace
from Products.CMFCore.utils import getToolByName
from z3c.formwidget.query.interfaces import IQuerySource
from zope.component.hooks import getSite
from zope.interface import classProvides
from zope.interface import directlyProvides
from zope.interface import implements
from zope.schema.interfaces import ISource, IContextSourceBinder
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary
from Products.CMFCore.utils import getToolByName

def find_workspace(context):
    while hasattr(context, 'context'):
        context = context.context
    for context in aq_chain(context):
        workspace = IWorkspace(context, None)
        if workspace is not None:
            return workspace

def TeamGroupsVocabulary(context):
    workspace = find_workspace(context)
    groups = set(workspace.available_groups.keys()) - set([u'Members'])
    return SimpleVocabulary.fromValues(sorted(groups))
directlyProvides(TeamGroupsVocabulary, IVocabularyFactory)


from plone.app.vocabularies.users import UsersVocabulary

from zope.schema.interfaces import IVocabularyFactory


def UsersFactory(object, query=""):
    context = getSite()
    users = getToolByName(context, "acl_users")
    return UsersVocabulary.fromItems(users.searchUsers(fullname=query), context)
