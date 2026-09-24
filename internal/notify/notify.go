package notify

import(
 "bytes"
 "context"
 "crypto/tls"
 "encoding/json"
 "fmt"
 "net"
 "net/http"
 "net/smtp"
 "strings"
 "time"
 "github.com/brainscan1980/Keepalived-Monitor/internal/config"
 "github.com/brainscan1980/Keepalived-Monitor/internal/monitor"
)

type Notifier interface{Send(context.Context,monitor.Incident)error}
type Multi struct{items []Notifier}
func New(c config.Notifications)*Multi{m:=&Multi{};if c.SMTP.Enabled{m.items=append(m.items,&mail{cfg:c.SMTP})};if c.Telegram.Enabled{m.items=append(m.items,&telegram{cfg:c.Telegram,client:&http.Client{Timeout:10*time.Second}})};return m}
func(m *Multi)Send(ctx context.Context,i monitor.Incident)error{var errs []string;for _,n:=range m.items{if err:=n.Send(ctx,i);err!=nil{errs=append(errs,err.Error())}};if len(errs)>0{return fmt.Errorf("notification errors: %s",strings.Join(errs,"; "))};return nil}
func(m *Multi)Enabled()bool{return len(m.items)>0}
func subject(i monitor.Incident)string{return fmt.Sprintf("[Keepalived Monitor] %s: %s",i.Type,i.Scope)}
func body(i monitor.Incident)string{s:=fmt.Sprintf("Event: %s\nScope: %s\nMessage: %s\n",i.Type,i.Scope,i.Message);if i.OldMaster!=""{s+="Old master: "+i.OldMaster+"\n"};if i.NewMaster!=""{s+="New master: "+i.NewMaster+"\n"};return s}

type mail struct{cfg config.SMTP}
func(m *mail)Send(ctx context.Context,i monitor.Incident)error{addr:=net.JoinHostPort(m.cfg.Host,fmt.Sprint(m.cfg.Port));d:=net.Dialer{Timeout:10*time.Second};conn,err:=d.DialContext(ctx,"tcp",addr);if err!=nil{return fmt.Errorf("smtp dial: %w",err)};defer conn.Close();c,err:=smtp.NewClient(conn,m.cfg.Host);if err!=nil{return err};defer c.Close();if m.cfg.StartTLS{if ok,_:=c.Extension("STARTTLS");!ok{return fmt.Errorf("smtp server does not support STARTTLS")};if err:=c.StartTLS(&tls.Config{ServerName:m.cfg.Host,MinVersion:tls.VersionTLS12});err!=nil{return err}};if m.cfg.Username!=""{if err:=c.Auth(smtp.PlainAuth("",m.cfg.Username,m.cfg.Password,m.cfg.Host));err!=nil{return err}};if err:=c.Mail(m.cfg.From);err!=nil{return err};for _,to:=range m.cfg.To{if err:=c.Rcpt(to);err!=nil{return err}};w,err:=c.Data();if err!=nil{return err};msg:="From: "+m.cfg.From+"\r\nTo: "+strings.Join(m.cfg.To,",")+"\r\nSubject: "+subject(i)+"\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n"+body(i);if _,err=w.Write([]byte(msg));err!=nil{return err};if err=w.Close();err!=nil{return err};return c.Quit()}

type telegram struct{cfg config.Telegram;client *http.Client}
func(t *telegram)Send(ctx context.Context,i monitor.Incident)error{payload,_:=json.Marshal(map[string]string{"chat_id":t.cfg.ChatID,"text":subject(i)+"\n\n"+body(i)});url:="https://api.telegram.org/bot"+t.cfg.BotToken+"/sendMessage";req,err:=http.NewRequestWithContext(ctx,http.MethodPost,url,bytes.NewReader(payload));if err!=nil{return err};req.Header.Set("Content-Type","application/json");resp,err:=t.client.Do(req);if err!=nil{return err};defer resp.Body.Close();if resp.StatusCode<200||resp.StatusCode>=300{return fmt.Errorf("telegram returned HTTP %d",resp.StatusCode)};return nil}
