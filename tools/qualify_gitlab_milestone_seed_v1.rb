# Minimal synthetic fixture for published WebArena-Verified GitLab task 590.
# Run only inside an isolated disposable GitLab CE 18.5 container.
# This does not reconstruct the original WebArena GitLab database.
require 'json'

root = User.find_by_username('root') or raise 'root user missing'
organization = Organizations::Organization.first or raise 'default organization missing'

group = Group.find_by_full_path('primer')
unless group
  response = Groups::CreateService.new(
    root,
    name: 'Primer',
    path: 'primer',
    visibility_level: Gitlab::VisibilityLevel::PRIVATE,
    organization_id: organization.id
  ).execute
  group = response.respond_to?(:payload) ? response.payload[:group] : response
end
raise "group invalid: #{group.errors.full_messages.join(', ')}" unless group.persisted?

project = Project.find_by_full_path('primer/design')
unless project
  project = Projects::CreateService.new(
    root,
    name: 'Design',
    path: 'design',
    namespace_id: group.id,
    visibility_level: Gitlab::VisibilityLevel::PRIVATE,
    initialize_with_readme: true
  ).execute
end
raise "project invalid: #{project.errors.full_messages.join(', ')}" unless project.persisted?

puts JSON.generate({ group_id: group.id, group_path: group.full_path,
                     project_id: project.id, project_path: project.full_path })
