package storage

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"time"

	_ "modernc.org/sqlite"
)

type Store struct { db *sql.DB }
type Event struct { ID int64 `json:"id"`; Timestamp string `json:"ts"`; Name string `json:"name"`; OldMaster string `json:"old_master"`; NewMaster string `json:"new_master"` }
type Incident struct { ID int64 `json:"id"`; Timestamp string `json:"ts"`; Type string `json:"type"`; Scope string `json:"scope"`; Message string `json:"message"`; OldMaster string `json:"old_master,omitempty"`; NewMaster string `json:"new_master,omitempty"` }

func Open(path string)(*Store,error){if err:=os.MkdirAll(filepath.Dir(path),0755);err!=nil{return nil,fmt.Errorf("create database directory: %w",err)};db,err:=sql.Open("sqlite",path);if err!=nil{return nil,fmt.Errorf("open sqlite: %w",err)};db.SetMaxOpenConns(1);s:=&Store{db:db};if err:=s.init();err!=nil{db.Close();return nil,err};return s,nil}
func(s *Store)init()error{_,err:=s.db.Exec(`CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, master TEXT); CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, name TEXT, old_master TEXT, new_master TEXT); CREATE INDEX IF NOT EXISTS idx_events_id ON events(id DESC); CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, type TEXT NOT NULL, scope TEXT NOT NULL, message TEXT NOT NULL, old_master TEXT, new_master TEXT); CREATE INDEX IF NOT EXISTS idx_incidents_id ON incidents(id DESC);`);if err!=nil{return fmt.Errorf("initialize sqlite: %w",err)};return nil}
func(s *Store)Close()error{return s.db.Close()}
func(s *Store)RecordMaster(name,master string)(bool,string,error){tx,err:=s.db.Begin();if err!=nil{return false,"",err};defer tx.Rollback();var old string;err=tx.QueryRow("SELECT COALESCE(master,'') FROM state WHERE name=?",name).Scan(&old);if err==sql.ErrNoRows{if _,err=tx.Exec("INSERT INTO state(name,master) VALUES(?,?)",name,master);err!=nil{return false,"",err};return false,"",tx.Commit()};if err!=nil{return false,"",err};if old==master{return false,old,tx.Commit()};if _,err=tx.Exec("UPDATE state SET master=? WHERE name=?",master,name);err!=nil{return false,old,err};if _,err=tx.Exec("INSERT INTO events(ts,name,old_master,new_master) VALUES(?,?,?,?)",time.Now().Format(time.RFC3339),name,old,master);err!=nil{return false,old,err};return true,old,tx.Commit()}
func(s *Store)RecordIncident(kind,scope,message,oldMaster,newMaster string)error{_,err:=s.db.Exec("INSERT INTO incidents(ts,type,scope,message,old_master,new_master) VALUES(?,?,?,?,?,?)",time.Now().Format(time.RFC3339),kind,scope,message,oldMaster,newMaster);return err}
func(s *Store)Events(limit int)([]Event,error){if limit<1{limit=50};if limit>500{limit=500};rows,err:=s.db.Query("SELECT id,ts,name,COALESCE(old_master,''),COALESCE(new_master,'') FROM events ORDER BY id DESC LIMIT ?",limit);if err!=nil{return nil,err};defer rows.Close();result:=make([]Event,0,limit);for rows.Next(){var e Event;if err:=rows.Scan(&e.ID,&e.Timestamp,&e.Name,&e.OldMaster,&e.NewMaster);err!=nil{return nil,err};result=append(result,e)};return result,rows.Err()}
func(s *Store)Incidents(limit int)([]Incident,error){if limit<1{limit=50};if limit>500{limit=500};rows,err:=s.db.Query("SELECT id,ts,type,scope,message,COALESCE(old_master,''),COALESCE(new_master,'') FROM incidents ORDER BY id DESC LIMIT ?",limit);if err!=nil{return nil,err};defer rows.Close();result:=make([]Incident,0,limit);for rows.Next(){var i Incident;if err:=rows.Scan(&i.ID,&i.Timestamp,&i.Type,&i.Scope,&i.Message,&i.OldMaster,&i.NewMaster);err!=nil{return nil,err};result=append(result,i)};return result,rows.Err()}
