from .role import Role
from .user import User

from .goal import Goal

from .supervisor import Supervisor
from .store import Store
from .advisor import Advisor

from .line import Line
from .category import Category
from .product import Product
from .sale import Sale

from .compliance import Compliance
from .region import Region
from app.models.advisor_performance import AdvisorPerformance
from app.models.store_line_goal import StoreLineGoal
from .meta_line import MetaLine
from app.models.sales_history_line import SalesHistoryLine
from app.models.conversion_diaria import ConversionDiaria
from .advisor_goal import AdvisorGoal
from app.models.uploaded_file import UploadedFile
from app.models.archivo_importado import ArchivoImportado

# Nuevos modelos para notificaciones
from app.models.notification import Notification
from app.models.notification_read import NotificationRead
from .daily_sales import DailySales
from .daily_store_sales import DailyStoreSales
from .checklist import ChecklistVisita
from .trafico_horario import TraficoCarga, TraficoHorario

# Metas mensuales de tienda (Sprint 2)
from app.models.meta_tienda import MetaTienda, MetaTiendaHistorial
