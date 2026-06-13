package client

import (
	"fmt"

	"github.com/PuerkitoBio/goquery"
	"net/http"
	"io"
)

// HTMLParser - заглушка для парсинга HTML (если API недоступен)
// Этот модуль используется как fallback, когда JSON API недоступен

// ParseLoginResponse парсит HTML ответ авторизации
func ParseLoginResponse(body io.Reader) (*LoginResponse, error) {
	doc, err := goquery.NewDocumentFromReader(body)
	if err != nil {
		return nil, fmt.Errorf("ошибка парсинга HTML: %w", err)
	}

	// TODO: Реализуйте парсинг конкретных элементов HTML
	// Пример:
	// success := doc.Find(".login-success").Text() == "true"
	// token := doc.Find("input[name='token']").AttrOr("value", "")

	return &LoginResponse{
		Success: true,
		Token:   "dummy-token",
		Message: "HTML login parsed",
	}, nil
}

// ParseSchedule парсит HTML расписания
func ParseSchedule(body io.Reader) ([]ScheduleEntry, error) {
	doc, err := goquery.NewDocumentFromReader(body)
	if err != nil {
		return nil, fmt.Errorf("ошибка парсинга HTML расписания: %w", err)
	}

	var schedule []ScheduleEntry

	// TODO: Реализуйте парсинг таблицы расписания
	// Пример:
	// doc.Find("table.schedule tr").Each(func(i int, s *goquery.Selection) {
	//     if i == 0 { return } // пропускаем заголовок
	//     entry := ScheduleEntry{
	//         Subject: s.Find("td.subject").Text(),
	//         Time:    s.Find("td.time").Text(),
	//         // ...
	//     }
	//     schedule = append(schedule, entry)
	// })

	return schedule, nil
}

// ParseGrades парсит HTML оценок
func ParseGrades(body io.Reader) ([]Grade, error) {
	doc, err := goquery.NewDocumentFromReader(body)
	if err != nil {
		return nil, fmt.Errorf("ошибка парсинга HTML оценок: %w", err)
	}

	var grades []Grade

	// TODO: Реализуйте парсинг таблицы оценок
	// Пример:
	// doc.Find("table.grades tr").Each(func(i int, s *goquery.Selection) {
	//     if i == 0 { return }
	//     grade := Grade{
	//         Subject: s.Find("td.subject").Text(),
	//         Value:   s.Find("td.grade").Text(),
	//         // ...
	//     }
	//     grades = append(grades, grade)
	// })

	return grades, nil
}

// ParseHomeworks парсит HTML домашних заданий
func ParseHomeworks(body io.Reader) ([]Homework, error) {
	doc, err := goquery.NewDocumentFromReader(body)
	if err != nil {
		return nil, fmt.Errorf("ошибка парсинга HTML домашних заданий: %w", err)
	}

	var homeworks []Homework

	// TODO: Реализуйте парсинг списка домашних заданий
	// Пример:
	// doc.Find(".homework-item").Each(func(i int, s *goquery.Selection) {
	//     hw := Homework{
	//         Subject:     s.Find(".subject").Text(),
	//         Description: s.Find(".description").Text(),
	//         // ...
	//     }
	//     homeworks = append(homeworks, hw)
	// })

	return homeworks, nil
}

// FetchHTMLPage делает GET запрос и возвращает HTML
func (c *EdonishClient) FetchHTMLPage(url string) (io.ReadCloser, error) {
	resp, err := c.httpClient.Get(url)
	if err != nil {
		return nil, fmt.Errorf("ошибка выполнения запроса: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		resp.Body.Close()
		return nil, fmt.Errorf("ошибка: HTTP %d", resp.StatusCode)
	}

	return resp.Body, nil
}
