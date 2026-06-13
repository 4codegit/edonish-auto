// Package edonish содержит клиент API для edonish.tj.
// ВСЯ логика взаимодействия с API инкапсулирована здесь.
// Запрещены импорты пакетов UI (fyne) — только net/http, encoding/json и т.д.
package edonish

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/4codegit/edonish-auto/internal/config"
)

// EdonishClient — основной клиент для работы с API edonish.tj
// Инкапсулирует HTTP-клиент, токены авторизации и данные пользователя
type EdonishClient struct {
	httpClient   *http.Client // HTTP-клиент с таймаутами
	JWTToken     string       // JWT-токен для авторизации
	RefreshToken string       // Refresh-токен для обновления JWT
	UserInfo     *UserInfo    // Информация о пользователе
	SchoolID     int          // ID выбранной школы
	Role         string       // Роль пользователя (teacher, director и т.д.)
	RolePrefix   string       // Префикс API для роли (из config.RolePrefixMap)
	Schools      []School     // Доступные школы/роли
}

// UserInfo — данные пользователя из ответа логина
type UserInfo struct {
	UID       int    `json:"uid"`        // ID пользователя
	FirstName string `json:"first_name"` // Имя
	LastName  string `json:"last_name"`  // Фамилия
}

// LoginResponse — ответ API при успешной авторизации
type LoginResponse struct {
	JWTToken     string `json:"jwt_token"`     // JWT-токен
	RefreshToken string `json:"refresh_token"` // Refresh-токен
	UID          int    `json:"uid"`           // ID пользователя
	FirstName    string `json:"first_name"`    // Имя
	LastName     string `json:"last_name"`     // Фамилия
}

// School — информация о школе/роли из header/info
type School struct {
	SchoolID   int    `json:"schoolId"`   // ID школы
	Name       string `json:"name"`       // Название роли
	SchoolName string `json:"schoolName"` // Название школы
}

// HeaderInfoResponse — элемент массива ответа /auth/v1/header/info
type HeaderInfoResponse struct {
	SchoolID   int    `json:"schoolId"`
	Name       string `json:"name"`
	SchoolName string `json:"schoolName"`
}

// JournalOptions — ответ OPTIONS /journal (группы с предметами и четвертями)
type JournalOptions struct {
	Groups []JournalGroup `json:"groups"`
}

// JournalGroup — группа (класс) в журнале
type JournalGroup struct {
	ID       int       `json:"id"`       // ID группы
	Name     string    `json:"name"`     // Название (номер + буква)
	Subjects []Subject `json:"subjects"` // Предметы класса
	Quarters []Quarter `json:"quarters"` // Четверти учебного года
}

// Subject — предмет в журнале
type Subject struct {
	SubjectID   int    `json:"subjectId"`   // ID предмета
	SubjectName string `json:"subjectName"` // Название предмета
}

// Quarter — четверть учебного года
type Quarter struct {
	ID             int    `json:"id"`             // ID → quarterPropertyId
	Name           string `json:"name"`           // Название четверти
	CurrentQuarter bool   `json:"currentQuarter"` // Текущая четверть?
}

// JournalStudent — ученик с оценками
type JournalStudent struct {
	StudentID    int           `json:"studentId"`    // ID ученика
	FirstName    string        `json:"firstName"`    // Имя
	LastName     string        `json:"lastName"`     // Фамилия
	SubjectMarks []SubjectMark `json:"subjectMarks"` // Оценки по датам
}

// SubjectMark — оценка ученика за определённую дату
type SubjectMark struct {
	AssignmentDateID string `json:"assignmentDateId"` // ID даты (строка!)
	Mark             int    `json:"mark"`             // Оценка (0 = нет оценки)
	ID               int    `json:"id"`               // ID оценки (markID, 0 = нет)
	ShortName        string `json:"shortName"`        // Краткое название типа оценки
}

// JournalDate — дата в журнале
type JournalDate struct {
	AssignmentDateID string `json:"assignmentDateId"` // ID даты
	AssignmentDate   string `json:"assignmentDate"`   // Дата в формате YYYY-MM-DD HH:MM:SS
}

// CreateMarkRequest — тело запроса на создание оценки
type CreateMarkRequest struct {
	MarkTypeGroupSubgroupStudentID int    `json:"mark_type_id"`              // Тип оценки (8)
	GroupSubgroupStudentID         int    `json:"group_subgroup_student_id"` // ID ученика в группе
	ScheduleDateID                 string `json:"schedule_date_id"`          // ID даты
	QuarterPropertyID              int    `json:"quarter_property_id"`       // ID четверти
	Mark                           int    `json:"mark"`                      // Оценка 1-10
	Signature                      string `json:"signature"`                 // Подпись
}

// CreateQuarterMarkRequest — тело запроса на создание четвертной оценки
type CreateQuarterMarkRequest struct {
	GroupSubgroupStudentID int `json:"group_subgroup_student_id"` // ID ученика в группе
	QuarterPropertyID      int `json:"quarter_property_id"`       // ID четверти
	Mark                   int `json:"mark"`                      // Оценка 1-10
}

// CreateSemesterMarkRequest — тело запроса на создание семестровой оценки
type CreateSemesterMarkRequest struct {
	GroupSubgroupStudentID int `json:"group_subgroup_student_id"` // ID ученика в группе
	SemesterPropertyID     int `json:"semester_property_id"`      // ID семестра
	Mark                   int `json:"mark"`                      // Оценка 1-10
}

// CreateYearMarkRequest — тело запроса на создание годовой оценки
type CreateYearMarkRequest struct {
	GroupSubgroupStudentID int `json:"group_subgroup_student_id"` // ID ученика в группе
	YearPropertyID         int `json:"year_property_id"`          // ID годовой
	Mark                   int `json:"mark"`                      // Оценка 1-10
}

// NewEdonishClient создаёт новый клиент API с настройками по умолчанию
func NewEdonishClient() *EdonishClient {
	return &EdonishClient{
		httpClient: &http.Client{
			Timeout: 30 * time.Second, // Таймаут 30 секунд на запрос
		},
	}
}

// Login выполняет авторизацию через API edonish.tj
// Возвращает ошибку при неудачной авторизации
func (c *EdonishClient) Login(login, password string) error {
	// Формируем тело запроса
	body := map[string]string{
		"login":    login,
		"password": password,
	}
	jsonBody, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("ошибка кодирования запроса: %w", err)
	}

	// Выполняем POST-запрос к API логина
	resp, err := c.httpClient.Post(config.APILogin, "application/json", bytes.NewBuffer(jsonBody))
	if err != nil {
		return fmt.Errorf("ошибка подключения к серверу: %w", err)
	}
	defer resp.Body.Close()

	// Читаем ответ
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("ошибка чтения ответа: %w", err)
	}

	// Проверяем статус-код
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("ошибка авторизации (код %d): %s", resp.StatusCode, string(respBody))
	}

	// Разбираем JSON-ответ
	var loginResp LoginResponse
	if err := json.Unmarshal(respBody, &loginResp); err != nil {
		return fmt.Errorf("ошибка разбора ответа: %w", err)
	}

	// Сохраняем токены и информацию о пользователе
	c.JWTToken = loginResp.JWTToken
	c.RefreshToken = loginResp.RefreshToken
	c.UserInfo = &UserInfo{
		UID:       loginResp.UID,
		FirstName: loginResp.FirstName,
		LastName:  loginResp.LastName,
	}

	return nil
}

// FetchHeaderInfo получает информацию о ролях/школах пользователя
// Вызывается после успешного логина для определения доступных школ
func (c *EdonishClient) FetchHeaderInfo() error {
	// Формируем URL с параметрами
	u, err := url.Parse(config.APIHeaderInfo)
	if err != nil {
		return fmt.Errorf("ошибка парсинга URL: %w", err)
	}
	q := u.Query()
	q.Set("lang", fmt.Sprintf("%d", config.LangRU))
	u.RawQuery = q.Encode()

	// Создаём GET-запрос с авторизацией
	req, err := http.NewRequest("GET", u.String(), nil)
	if err != nil {
		return fmt.Errorf("ошибка создания запроса: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.JWTToken)

	// Выполняем запрос
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("ошибка запроса: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("ошибка чтения ответа: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("ошибка получения данных (код %d): %s", resp.StatusCode, string(respBody))
	}

	// Разбираем массив школ/ролей
	var headerInfo []HeaderInfoResponse
	if err := json.Unmarshal(respBody, &headerInfo); err != nil {
		return fmt.Errorf("ошибка разбора ответа: %w", err)
	}

	// Преобразуем в структуру School
	c.Schools = make([]School, 0, len(headerInfo))
	for _, hi := range headerInfo {
		c.Schools = append(c.Schools, School{
			SchoolID:   hi.SchoolID,
			Name:       hi.Name,
			SchoolName: hi.SchoolName,
		})
	}

	return nil
}

// SelectSchool выбирает школу и устанавливает роль/префикс
// Должна вызываться после FetchHeaderInfo
func (c *EdonishClient) SelectSchool(schoolID int) error {
	// Ищем выбранную школу в списке доступных
	for _, school := range c.Schools {
		if school.SchoolID == schoolID {
			c.SchoolID = schoolID
			c.Role = school.Name
			// Определяем префикс API по роли
			if prefix, ok := config.RolePrefixMap[school.Name]; ok {
				c.RolePrefix = prefix
			} else {
				// Если роль неизвестна, используем префикс teacher по умолчанию
				c.RolePrefix = "/teacher/v1"
			}
			return nil
		}
	}
	return fmt.Errorf("школа с ID %d не найдена в списке доступных", schoolID)
}

// RefreshJWT обновляет JWT-токен с помощью refresh-токена
// Вызывается автоматически при истечении JWT
func (c *EdonishClient) RefreshJWT() error {
	req, err := http.NewRequest("GET", config.APIRefresh, nil)
	if err != nil {
		return fmt.Errorf("ошибка создания запроса: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.RefreshToken)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("ошибка обновления токена: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("ошибка чтения ответа: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("ошибка обновления токена (код %d): %s", resp.StatusCode, string(respBody))
	}

	var result struct {
		JWTToken string `json:"jwt_token"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return fmt.Errorf("ошибка разбора ответа: %w", err)
	}

	c.JWTToken = result.JWTToken
	return nil
}

// apiURL строит полный URL для запроса к API журнала
// Добавляет school_id и lang к параметрам
func (c *EdonishClient) apiURL(path string, params map[string]string) string {
	base := config.APIBase + c.RolePrefix + path
	u, _ := url.Parse(base)
	q := u.Query()
	q.Set("school_id", fmt.Sprintf("%d", c.SchoolID))
	q.Set("lang", fmt.Sprintf("%d", config.LangRU))
	for k, v := range params {
		q.Set(k, v)
	}
	u.RawQuery = q.Encode()
	return u.String()
}

// doRequest выполняет HTTP-запрос с авторизацией
// Автоматически обновляет токен при 401 и повторяет запрос
func (c *EdonishClient) doRequest(method, url string, body interface{}) ([]byte, int, error) {
	var reqBody io.Reader
	if body != nil {
		jsonData, err := json.Marshal(body)
		if err != nil {
			return nil, 0, fmt.Errorf("ошибка кодирования тела запроса: %w", err)
		}
		reqBody = bytes.NewBuffer(jsonData)
	}

	req, err := http.NewRequest(method, url, reqBody)
	if err != nil {
		return nil, 0, fmt.Errorf("ошибка создания запроса: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.JWTToken)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("ошибка выполнения запроса: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, fmt.Errorf("ошибка чтения ответа: %w", err)
	}

	// Если токен истёк — пробуем обновить и повторить запрос
	if resp.StatusCode == http.StatusUnauthorized {
		if err := c.RefreshJWT(); err != nil {
			return nil, resp.StatusCode, fmt.Errorf("токен истёк, не удалось обновить: %w", err)
		}
		// Повторяем запрос с новым токеном
		req.Header.Set("Authorization", "Bearer "+c.JWTToken)
		if body != nil {
			jsonData, _ := json.Marshal(body)
			req.Body = io.NopCloser(bytes.NewBuffer(jsonData))
			req.GetBody = func() (io.ReadCloser, error) {
				return io.NopCloser(bytes.NewBuffer(jsonData)), nil
			}
		}
		resp2, err := c.httpClient.Do(req)
		if err != nil {
			return nil, 0, fmt.Errorf("ошибка повторного запроса: %w", err)
		}
		defer resp2.Body.Close()
		respBody, err = io.ReadAll(resp2.Body)
		if err != nil {
			return nil, resp2.StatusCode, fmt.Errorf("ошибка чтения ответа: %w", err)
		}
		return respBody, resp2.StatusCode, nil
	}

	return respBody, resp.StatusCode, nil
}

// GetJournalOptions получает список групп (классов) с предметами и четвертями
// Это OPTIONS-запрос к /journal
func (c *EdonishClient) GetJournalOptions() (*JournalOptions, error) {
	url := c.apiURL("/journal", nil)
	respBody, statusCode, err := c.doRequest("OPTIONS", url, nil)
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("ошибка получения журнала (код %d): %s", statusCode, string(respBody))
	}

	var opts JournalOptions
	if err := json.Unmarshal(respBody, &opts); err != nil {
		return nil, fmt.Errorf("ошибка разбора ответа журнала: %w", err)
	}

	return &opts, nil
}

// GetJournalDates получает список дат для предмета в четверти
// groupID — ID класса, subjectID — ID предмета, quarterPropertyID — ID четверти
func (c *EdonishClient) GetJournalDates(groupID, subjectID, quarterPropertyID int) ([]JournalDate, error) {
	params := map[string]string{
		"group_id":            fmt.Sprintf("%d", groupID),
		"subject_id":          fmt.Sprintf("%d", subjectID),
		"quarter_property_id": fmt.Sprintf("%d", quarterPropertyID),
	}
	url := c.apiURL("/journal/dates", params)

	respBody, statusCode, err := c.doRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("ошибка получения дат (код %d): %s", statusCode, string(respBody))
	}

	var dates []JournalDate
	if err := json.Unmarshal(respBody, &dates); err != nil {
		return nil, fmt.Errorf("ошибка разбора дат: %w", err)
	}

	return dates, nil
}

// GetJournalStudents получает список учеников с оценками
// groupID — ID класса, subjectID — ID предмета, quarterPropertyID — ID четверти
func (c *EdonishClient) GetJournalStudents(groupID, subjectID, quarterPropertyID int) ([]JournalStudent, error) {
	params := map[string]string{
		"group_id":            fmt.Sprintf("%d", groupID),
		"subject_id":          fmt.Sprintf("%d", subjectID),
		"quarter_property_id": fmt.Sprintf("%d", quarterPropertyID),
	}
	url := c.apiURL("/journal/students", params)

	respBody, statusCode, err := c.doRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("ошибка получения учеников (код %d): %s", statusCode, string(respBody))
	}

	var students []JournalStudent
	if err := json.Unmarshal(respBody, &students); err != nil {
		return nil, fmt.Errorf("ошибка разбора учеников: %w", err)
	}

	return students, nil
}

// CreateMark создаёт оценку за урок для ученика
// studentID — ID ученика в группе, dateID — ID даты, quarterID — ID четверти, mark — оценка (1-10)
func (c *EdonishClient) CreateMark(studentID int, dateID string, quarterID, mark int) error {
	reqBody := CreateMarkRequest{
		MarkTypeGroupSubgroupStudentID: config.MarkTypeID,
		GroupSubgroupStudentID:         studentID,
		ScheduleDateID:                 dateID,
		QuarterPropertyID:              quarterID,
		Mark:                           mark,
		Signature:                      config.Signature,
	}

	url := c.apiURL("/journal/10_point_mark/create", nil)
	respBody, statusCode, err := c.doRequest("POST", url, reqBody)
	if err != nil {
		return err
	}

	if statusCode != http.StatusOK && statusCode != http.StatusCreated {
		return fmt.Errorf("ошибка создания оценки (код %d): %s", statusCode, string(respBody))
	}

	return nil
}

// DeleteMark удаляет оценку по её ID
func (c *EdonishClient) DeleteMark(markID int) error {
	params := map[string]string{
		"mark_id": fmt.Sprintf("%d", markID),
	}
	url := c.apiURL("/journal/mark/delete", params)

	respBody, statusCode, err := c.doRequest("POST", url, nil)
	if err != nil {
		return err
	}

	if statusCode != http.StatusOK && statusCode != http.StatusCreated {
		return fmt.Errorf("ошибка удаления оценки (код %d): %s", statusCode, string(respBody))
	}

	return nil
}

// CreateQuarterMark создаёт четвертную оценку
func (c *EdonishClient) CreateQuarterMark(studentID, quarterID, mark int) error {
	reqBody := CreateQuarterMarkRequest{
		GroupSubgroupStudentID: studentID,
		QuarterPropertyID:      quarterID,
		Mark:                   mark,
	}

	url := c.apiURL("/journal/10_point_quarter_mark/create", nil)
	respBody, statusCode, err := c.doRequest("POST", url, reqBody)
	if err != nil {
		return err
	}

	if statusCode != http.StatusOK && statusCode != http.StatusCreated {
		return fmt.Errorf("ошибка создания четвертной оценки (код %d): %s", statusCode, string(respBody))
	}

	return nil
}

// CreateSemesterMark создаёт семестровую оценку
func (c *EdonishClient) CreateSemesterMark(studentID, semesterID, mark int) error {
	reqBody := CreateSemesterMarkRequest{
		GroupSubgroupStudentID: studentID,
		SemesterPropertyID:     semesterID,
		Mark:                   mark,
	}

	url := c.apiURL("/journal/10_point_semester/create", nil)
	respBody, statusCode, err := c.doRequest("POST", url, reqBody)
	if err != nil {
		return err
	}

	if statusCode != http.StatusOK && statusCode != http.StatusCreated {
		return fmt.Errorf("ошибка создания семестровой оценки (код %d): %s", statusCode, string(respBody))
	}

	return nil
}

// CreateYearMark создаёт годовую оценку
func (c *EdonishClient) CreateYearMark(studentID, yearID, mark int) error {
	reqBody := CreateYearMarkRequest{
		GroupSubgroupStudentID: studentID,
		YearPropertyID:         yearID,
		Mark:                   mark,
	}

	url := c.apiURL("/journal/10_point_year/create", nil)
	respBody, statusCode, err := c.doRequest("POST", url, reqBody)
	if err != nil {
		return err
	}

	if statusCode != http.StatusOK && statusCode != http.StatusCreated {
		return fmt.Errorf("ошибка создания годовой оценки (код %d): %s", statusCode, string(respBody))
	}

	return nil
}

// FullName возвращает полное имя пользователя (Фамилия Имя)
func (u *UserInfo) FullName() string {
	if u == nil {
		return ""
	}
	return u.LastName + " " + u.FirstName
}
