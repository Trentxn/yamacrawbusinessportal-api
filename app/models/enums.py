import enum


class UserRole(str, enum.Enum):
    system_admin = "system_admin"
    admin = "admin"
    business_owner = "business_owner"
    contractor = "contractor"
    public_user = "public_user"


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    pending_verification = "pending_verification"


class ListingType(str, enum.Enum):
    business = "business"
    contractor = "contractor"


class BusinessStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"
    archived = "archived"


class ServiceRequestStatus(str, enum.Enum):
    open = "open"
    read = "read"
    replied = "replied"
    closed = "closed"
    spam = "spam"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    flagged = "flagged"


class ModerationAction(str, enum.Enum):
    flag = "flag"
    dismiss = "dismiss"
    warn = "warn"
    suspend = "suspend"
    ban = "ban"


class NotificationType(str, enum.Enum):
    approval = "approval"
    rejection = "rejection"
    inquiry = "inquiry"
    system = "system"
    review = "review"


class UploadType(str, enum.Enum):
    logo = "logo"
    photo = "photo"
    document = "document"


class AuditAction(str, enum.Enum):
    login = "login"
    logout = "logout"
    create = "create"
    update = "update"
    delete = "delete"
    approve = "approve"
    reject = "reject"
    suspend = "suspend"
