# Import all built-in templates here to trigger their @register decorators.
from team_maker.templates.software_delivery.template import SoftwareDeliveryTemplate  # noqa: F401
from team_maker.templates.education.template import EducationTeamTemplate  # noqa: F401
from team_maker.templates.research_content.template import ResearchContentTeamTemplate  # noqa: F401

__all__ = ["SoftwareDeliveryTemplate", "EducationTeamTemplate", "ResearchContentTeamTemplate"]
