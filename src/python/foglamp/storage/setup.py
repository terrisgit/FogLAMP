
from threading import Thread
from time import sleep

import threading
from queue import Queue

import asyncio
import psycopg2
import uuid
from enum import IntEnum


class messagestate(IntEnum):
    uploaded=0
    ready=1
    done=2


class storage(object):

    def __init__(self):
        self.q = Queue()

    def get_queue(self):
        return self.q


    def put_message(self, msg):
        self.q.put(msg)


class upload_queue:           #just move to read queue
    def __init__(self, conn):
        self.conn=conn

    def process(self, message_id):  #this is code to actually unpak the message
        cur = self.conn.cursor()
        print("message moved to ready queue "+ str(int( messagestate.ready)))
        cur.execute("update message_queue set reader_id=NULL, state = "+ str(int( messagestate.ready)) + " where message_id ='" + str(message_id) + "'")


class ready_queue:
    def __init__(self, conn):
        self.conn=conn

    def process(self, message_id):  #this is code to actually unpak the message
        cur = self.conn.cursor()
        cur.execute("select message_queue from message_queue where message_id ='" + str(message_id) + "'")
        row = cur.fetchone()
        print(row) #for now just print the message
        cur.execute("update message_queue set reader_id=NULL, state = "+str(int(messagestate.done)) + " where message_id ='" + str(message_id) + "'")
        print("message moved to done queue")




class storage_engine:
    def __init__(self, connection_string, stor):
        self.running=True
        self.conn = psycopg2.connect("host='localhost' dbname='foglamp' user='foglamp' password='foglamp'")
        self.conn.set_session(autocommit=True)
        self.reader_id= uuid.uuid1()
        self.store=stor
        self.rq=ready_queue(self.conn)
        self.uq=upload_queue(self.conn)

    def save_message(self, msg):
        cur = self.conn.cursor()
        cur.execute("insert into message_queue (state,reader_id,message_data) values(0, NULL,'blah')")


    def next_message(self):
        cur = self.conn.cursor()
        cur.execute("select message_id from message_queue where reader_id ='" + str(self.reader_id) + "'")
        row = cur.fetchone()
        if row is None:
            return 0
        else:
            return row[0]

    def get_state(self, id):
        cur = self.conn.cursor()
        cur.execute("select state from message_queue where message_id ='" + str(id) + "'")
        row = cur.fetchone()
        return row[0]

    def get_batch(self):
        cur = self.conn.cursor()
        cur.execute("update message_queue set reader_id='" + str(self.reader_id) + "' where state <"+ str(int( messagestate.done)) + " and reader_id is NULL")



    def process(self,message_id):
        state = self.get_state(message_id)

        if(state==messagestate.uploaded):
            self.uq.process(message_id)
        elif (state==messagestate.ready):
            self.rq.process(message_id)
        elif (state==messagestate.done):
            pass
        else:
            pass #do the default


class worker_thread(threading.Thread):
    def __init__(self, se):
        threading.Thread.__init__(self)
        self.se = se
        self.running=True


    def run(self):
        print ("Starting worker thread")
        while self.running:  #thread will loop until stopped

            # first lets insert all messages added to storage to the db message_queue
            try:
                while True:
                    message = self.se.store.get_queue().get_nowait()
                    self.se.save_message(message)

            except Exception as e:
                pass


            self.se.get_batch()  #grab a batch of mesages for processing


            message_id = self.se.next_message()
            if message_id > 0:
                self.se.process(message_id)

            sleep(1)







async def main():






        print("connecting to the database")

        my_guid=uuid.uuid1()

        try:
            conn = psycopg2.connect("host='localhost' dbname='foglamp' user='foglamp' password='foglamp'")
            print("i have connected")

            #now create table

            cur = conn.cursor()
            try:
                cur.execute("drop table message_queue")
            except:
                conn.rollback()
                print("ignore drop")

            cur.execute("create table message_queue (message_id  serial primary key, state int, reader_id uuid, message_data bytea, create_time timestamp(6) with time zone NOT NULL DEFAULT now())")
            print("table created")

            # lets insert a message
            for i in range(0,10):
                cur.execute("insert into message_queue (state,reader_id,message_data) values(5,NULL,'blah')")

            conn.commit()

            # now mark rows that can get processed.
            # single thread will select all rows which are in a ready state
            cur.execute("update message_queue set reader_id='"+str(my_guid)+"' where state=6 and reader_id is NULL")


            conn.commit()


            # now grab the rows that belong to me
            cur.execute("select message_id,state from message_queue where reader_id ='"+str(my_guid)+"'" )
            for row in cur:
                print("row: "+ str(row[0]))


            #lets test the new message engine
            store = storage()  #used to add message. this is api

            store.put_message("blah1")
            store.put_message("blah2")

            se =storage_engine("host='localhost' dbname='foglamp' user='foglamp' password='foglamp'",store)

            wt = worker_thread(se)
            wt.start()

            sleep(10)  #sleep for a while
            print("Stopping queue engine")
            wt.running=False

            wt.join()  #wait for thread to end



        except Exception as e:
            print("Error: "+str(e))





if __name__ == "__main__":

    asyncio.get_event_loop().run_until_complete(main())











print("all Done.");

