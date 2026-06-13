// Package config содержит все константы, URL-адреса API и настройки приложения.
// Централизованное хранение конфигурации для удобства поддержки.
package config

// Название и версия приложения
const (
	AppName    = "eDonish Auto"
	AppVersion = "4.0.0"
	Signature  = "eDonish Auto by 4code" // Подпись для создаваемых оценок
)

// Базовые URL-адреса API edonish.tj
const (
	APIBase       = "https://api.edonish.tj"
	APILogin      = APIBase + "/auth/v1/login"
	APIRefresh    = APIBase + "/auth/v1/refresh_token"
	APIHeaderInfo = APIBase + "/auth/v1/header/info"
)

// Язык API (2 = русский)
const LangRU = 2

// Оценки по умолчанию
const (
	MinGrade = 8
	MaxGrade = 10
)

// Цветовая палитра приложения (HEX-коды)
const (
	ColorPrimary = "#2563EB" // Синий — основной акцент
	ColorSuccess = "#16A34A" // Зелёный — успех
	ColorError   = "#DC2626" // Красный — ошибка
	ColorWarning = "#D97706" // Оранжевый — предупреждение
	ColorInfo    = "#0891B2" // Бирюзовый — информация
	ColorMuted   = "#6B7280" // Серый — приглушённый текст
)

// Роль → префикс API для журнала
// Каждая роль использует свой префикс в URL-адресах API
var RolePrefixMap = map[string]string{
	"teacher":           "/teacher/v1",
	"classroom-teacher": "/teacher/v1",
	"school_admin":      "/school_admin/v1",
	"director":          "/director/v1",
	"headteacher":       "/headteacher/v1",
}

// SessionFile — имя файла для сохранения сессии (в домашней директории)
const SessionFile = ".edonish_session.json"

// MarkTypeID — тип оценки (8 = обычная оценка за урок)
const MarkTypeID = 8
