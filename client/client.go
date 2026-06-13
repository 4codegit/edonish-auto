package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"time"
)

// EdonishClient - клиент для работы с API портала edonish.tj
type EdonishClient struct {
	httpClient *http.Client
	baseURL    string
	authURL    string
}

// LoginRequest - структура запроса для авторизации
type LoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

// LoginResponse - структура ответа на запрос авторизации
type LoginResponse struct {
	Success bool   `json:"success"`
	Token   string `json:"token,omitempty"`
	Message string `json:"message,omitempty"`
}

// ScheduleEntry - запись расписания
type ScheduleEntry struct {
	ID        int    `json:"id"`
	Subject   string `json:"subject"`
	StartTime string `json:"start_time"`
	EndTime   string `json:"end_time"`
	Classroom string `json:"classroom"`
	Date      string `json:"date"`
	Teacher   string `json:"teacher"`
}

// Grade - оценка
type Grade struct {
	ID        int     `json:"id"`
	Subject   string  `json:"subject"`
	Value     string  `json:"value"`
	Date      string  `json:"date"`
	Teacher   string  `json:"teacher"`
	GradeType string  `json:"grade_type"` // например: "текущая", "итоговая"
	Weight    float64 `json:"weight"`
}

// Homework - домашнее задание
type Homework struct {
	ID          int    `json:"id"`
	Subject     string `json:"subject"`
	Description string `json:"description"`
	DueDate     string `json:"due_date"`
	Teacher     string `json:"teacher"`
	Attached    string `json:"attached,omitempty"` // ссылка на файл
}

// NewEdonishClient - создаёт новый клиент для работы с edonish.tj
func NewEdonishClient(baseURL, authURL string) (*EdonishClient, error) {
	// Создаём jar для хранения cookies
	jar, err := cookiejar.New(&cookiejar.Options{})
	if err != nil {
		return nil, fmt.Errorf("ошибка создания cookie jar: %w", err)
	}

	// Парсим URL для jar
	parsedURL, err := url.Parse(baseURL)
	if err != nil {
		return nil, fmt.Errorf("ошибка парсинга baseURL: %w", err)
	}

	// Устанавливаем cookies для домена
	jar.SetCookies(parsedURL, []*http.Cookie{})

	return &EdonishClient{
		httpClient: &http.Client{
			Jar:     jar,
			Timeout: 30 * time.Second,
		},
		baseURL: baseURL,
		authURL: authURL,
	}, nil
}

// Login выполняет авторизацию пользователя
func (c *EdonishClient) Login(ctx context.Context, username, password string) (*LoginResponse, error) {
	reqBody := LoginRequest{
		Username: username,
		Password: password,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("ошибка сериализации запроса: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.authURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("ошибка создания запроса: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ошибка выполнения запроса: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("ошибка чтения ответа: %w", err)
	}

	var loginResp LoginResponse
	if err := json.Unmarshal(body, &loginResp); err != nil {
		return nil, fmt.Errorf("ошибка парсинга JSON ответа: %w, тело ответа: %s", err, string(body))
	}

	if resp.StatusCode != http.StatusOK {
		return &loginResp, &LoginError{
			Message:  loginResp.Message,
			StatusCode: resp.StatusCode,
		}
	}

	return &loginResp, nil
}

// GetSchedule получает расписание пользователя
func (c *EdonishClient) GetSchedule(ctx context.Context, dateFrom, dateTo string) ([]ScheduleEntry, error) {
	// TODO: Замените на реальный эндпоинт API
	endpoint := fmt.Sprintf("%s/api/schedule?from=%s&to=%s", c.baseURL, dateFrom, dateTo)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("ошибка создания запроса расписания: %w", err)
	}

	req.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ошибка выполнения запроса расписания: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("ошибка чтения ответа расписания: %w", err)
	}

	var schedule []ScheduleEntry
	if err := json.Unmarshal(body, &schedule); err != nil {
		// Заглушка: возвращаем пустой массив при ошибке парсинга
		return []ScheduleEntry{}, fmt.Errorf("ошибка парсинга JSON расписания: %w, тело: %s", err, string(body))
	}

	return schedule, nil
}

// GetGrades получает оценки пользователя
func (c *EdonishClient) GetGrades(ctx context.Context, subject string) ([]Grade, error) {
	// TODO: Замените на реальный эндпоинт API
	endpoint := fmt.Sprintf("%s/api/grades?subject=%s", c.baseURL, subject)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("ошибка создания запроса оценок: %w", err)
	}

	req.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ошибка выполнения запроса оценок: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("ошибка чтения ответа оценок: %w", err)
	}

	var grades []Grade
	if err := json.Unmarshal(body, &grades); err != nil {
		return []Grade{}, fmt.Errorf("ошибка парсинга JSON оценок: %w, тело: %s", err, string(body))
	}

	return grades, nil
}

// GetHomeworks получает домашние задания
func (c *EdonishClient) GetHomeworks(ctx context.Context) ([]Homework, error) {
	// TODO: Замените на реальный эндпоинт API
	endpoint := fmt.Sprintf("%s/api/homeworks", c.baseURL)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("ошибка создания запроса домашних заданий: %w", err)
	}

	req.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ошибка выполнения запроса домашних заданий: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("ошибка чтения ответа домашних заданий: %w", err)
	}

	var homeworks []Homework
	if err := json.Unmarshal(body, &homeworks); err != nil {
		return []Homework{}, fmt.Errorf("ошибка парсинга JSON домашних заданий: %w, тело: %s", err, string(body))
	}

	return homeworks, nil
}

// IsAuthenticated проверяет, авторизован ли пользователь (проверка cookies)
func (c *EdonishClient) IsAuthenticated() bool {
	// Простая проверка: есть ли cookies для домена
	parsedURL, err := url.Parse(c.baseURL)
	if err != nil {
		return false
	}
	cookies := c.httpClient.Jar.Cookies(parsedURL)
	return len(cookies) > 0
}

// LoginError - ошибка авторизации
type LoginError struct {
	Message string
	StatusCode int
}

func (e *LoginError) Error() string {
	return fmt.Sprintf("ошибка авторизации: %s (HTTP %d)", e.Message, e.StatusCode)
}
