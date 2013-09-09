from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
from OFS.Cache import Cacheable
from Products.CMFCore.utils import getToolByName
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.PlonePAS.interfaces.group import IGroupIntrospection
from Products.PluggableAuthService.interfaces.plugins \
    import IGroupEnumerationPlugin
from Products.PluggableAuthService.interfaces.plugins \
    import IGroupsPlugin
from Products.PluggableAuthService.interfaces.plugins \
    import IPropertiesPlugin
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from borg.localrole.interfaces import ILocalRoleProvider
from collective.workspace.interfaces import IWorkspace
from zope.annotation.interfaces import IAnnotations
from zope.interface import implements


manage_addWorkspaceGroupManagerForm = PageTemplateFile(
    'templates/WorkspaceGroupManagerForm', globals(),
    __name__='manage_addWorkspaceGroupManagerForm')


def addWorkspaceGroupManager(dispatcher, id, title=None, REQUEST=None):
    """ Add a WorkspaceGroupManager to a Pluggable Auth Service. """

    pmm = WorkspaceGroupManager(id, title)
    dispatcher._setObject(pmm.getId(), pmm)

    if REQUEST is not None:
        REQUEST['RESPONSE'].redirect(
            '%s/manage_workspace?manage_tabs_message='
            'WorkspaceGroupManager+added.'
            % dispatcher.absolute_url())


WORKSPACE_INTERFACE = 'collective.workspace.interfaces.IHasWorkspace'


class WorkspaceGroupManager(BasePlugin, Cacheable):
    """PAS plugin to dynamically create groups from the team rosters."""

    meta_type = 'collective.workspace Group Manager'

    security = ClassSecurityInfo()

    implements(
        IGroupsPlugin,
        IGroupEnumerationPlugin,
        IGroupIntrospection,
        IPropertiesPlugin,
        )

    def __init__(self, id, title=None):
        self._id = self.id = id
        self.title = title

    def _iterWorkspaces(self):
        workspaces = IAnnotations(self.REQUEST).get('workspaces')
        if workspaces is None:
            catalog = getToolByName(self, 'portal_catalog')
            workspaces = [
                IWorkspace(b._unrestrictedGetObject())
                for b in catalog.unrestrictedSearchResults(
                    object_provides=WORKSPACE_INTERFACE
                    )
                ]
            IAnnotations(self.REQUEST)['workspaces'] = workspaces

        return iter(workspaces)

    def _getWorkspace(self, uid):
        catalog = getToolByName(self, 'portal_catalog')
        res = catalog.unrestrictedSearchResults(
            object_provides=WORKSPACE_INTERFACE,
            UID=uid
            )
        if not res:
            return

        return IWorkspace(res[0]._unrestrictedGetObject())

    #
    #   IGroupsPlugin implementation
    #
    def getGroupsForPrincipal(self, principal, request=None):
        # For each workspace:
        #   If workspace has this user:
        #      Return that user's workspace groups
        groups = []
        for workspace in self._iterWorkspaces():
            member_data = workspace.members.get(principal.getId())
            if member_data is not None:
                # Membership in the Members group is implied
                member_groups = set(member_data['groups']) | set([u'Members'])
                groups.extend([
                    '%s:%s' % (group_name, workspace.context.UID())
                    for group_name in member_groups
                    ])
        return tuple(groups)
    security.declarePrivate('getGroupsForPrincipal')

    #
    #   IGroupEnumerationPlugin implementation
    #
    def enumerateGroups(self,
                        id=None,
                        title=None,
                        exact_match=False,
                        sort_by=None,
                        max_results=None,
                        **kw
                        ):
        group_info = []
        plugin_id = self.getId()

        if id and isinstance(id, str):
            id = [id]

        if isinstance(title, str):
            title = [title]

        catalog = getToolByName(self, 'portal_catalog')
        query = {
            'object_provides': WORKSPACE_INTERFACE,
            'sort_on': 'sortable_title',
        }

        if id and ':' in id:
            target_group_name, workspace_uid = id.split(':')
            query['UID'] = workspace_uid

        elif title:
            query['Title'] = exact_match and title or \
                             ['%s*' % t for t in title if t]

        i = 0
        for brain in catalog.unrestrictedSearchResults(query):
            obj = brain._unrestrictedGetObject()
            workspace = IWorkspace(obj)
            for group_name in workspace.available_groups:
                i += 1
                if max_results is not None and i >= max_results:
                    break

                if id is None or group_name == target_group_name:
                    workspace_url = obj.absolute_url() + '/team-roster'
                    info = {
                        'id': group_name + ':' + brain.UID,
                        'title': group_name + ': ' + brain.Title,
                        'pluginid': plugin_id,
                        'properties_url': workspace_url,
                        'members_url': workspace_url,
                    }
                    group_info.append(info)
        return tuple(group_info)
    security.declarePrivate('enumerateGroups')

    #
    #   IGroupIntrospectionPlugin implementation
    #

    def getGroupById(self, group_id, default=None):
        if ':' not in group_id:
            return default
        pas = self._getPAS()
        plugins = pas._getOb('plugins')
        groups_plugin = pas.source_groups
        return groups_plugin._findGroup(plugins, group_id)
    security.declarePrivate('getGroupById')

    def getGroups(self):
        pas = self._getPAS()
        plugins = pas._getOb('plugins')
        groups_plugin = pas.source_groups

        groups = []
        for workspace in self._iterWorkspaces():
            for group_name in workspace.available_groups:
                group_id = group_name + ':' + workspace.context.UID()
                groups.append(groups_plugin._findGroup(plugins, group_id))
        return groups
    security.declarePrivate('getGroups')

    def getGroupIds(self):
        group_ids = []
        for workspace in self._iterWorkspaces():
            for group_name in workspace.available_groups:
                group_ids.append('%s:%s' %
                    (group_name, workspace.context.UID()))
        return group_ids
    security.declarePrivate('getGroupIds')

    def getGroupMembers(self, group_id):
        if ':' not in group_id:
            return ()

        group_name, workspace_uid = group_id.split(':')
        workspace = self._getWorkspace(workspace_uid)
        if workspace is not None:
            return tuple(
                u for u, data in workspace.members.items()
                if group_name in data['groups']
                # Membership in the Members group is implied
                or group_name == u'Members'
                )
        return ()
    security.declarePrivate('getGroupMembers')

    def getPropertiesForUser(self, user, request=None):
        group_id = user.getId()
        if ':' not in group_id:
            return {}

        group_name, workspace_uid = user.getId().split(':')
        workspace = self._getWorkspace(workspace_uid)
        if workspace is not None:
            if group_name in workspace.available_groups:
                return {'title':
                    group_name + ': ' + workspace.context.Title()}

        return {}
    security.declarePrivate('getPropertiesForUser')


InitializeClass(WorkspaceGroupManager)


class WorkspaceRoles(object):
    """Automatically assign local roles to workspace groups.
    """
    implements(ILocalRoleProvider)

    def __init__(self, context):
        self.workspace = IWorkspace(context)

    def getAllRoles(self):
        for group_name, roles in self.workspace.available_groups.items():
            group_id = group_name.encode('utf8') + ':' + self.workspace.context.UID()
            yield group_id, roles

    def getRoles(self, user_id):
        for group_id, group_roles in self.getAllRoles():
            if user_id == group_id:
                return group_roles
        return ()


# Make the MemberAdmin role show up on the Sharing tab
class TeamManagerRoleDelegation(object):
    title = u"Can edit roster"
    required_permission = "collective.workspace: Manage roster"
