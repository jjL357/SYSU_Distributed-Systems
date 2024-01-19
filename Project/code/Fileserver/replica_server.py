from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
from concurrent.futures import ThreadPoolExecutor
import os 
import shutil
import socketserver
import threading
import time
import msvcrt
import random


replica_dict = {} # 记录副本服务器和其端口号
replica_addr_dict = {} # 记录副本服务器和其文件夹地址
file_update_time = {} # 记录文件修改时间



class FileLock: # 文件锁
    def __init__(self, folder=None):
        self.directory = os.getcwd()

    def acquire_lock(self, filename): # 获取锁
        lock_file_path = os.path.join(self.directory, f'{filename}.lock')
        
        while True:
            try:
                lock_file = open(lock_file_path, "w")
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                return lock_file
            except Exception as e:
                print(f"Acquiring FileLock Error: ({filename}): {e}")
                time.sleep(1)  # 等待一段时间后重试

    def release_lock(self, lock_file): #释放锁
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception as e:
            print(f"Releasing FileLock Error: {e}")
        finally:
            lock_file.close()
            
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)
    
class FileService:# 服务器
    def __init__(self,addr=None,main=False): #初始化服务器
        self.server_files_directory = None 
        if addr is None:
            self.server_files_directory = os.getcwd()
        else :
            self.server_files_directory = os.path.join(os.getcwd(),addr)
            
        self.main_server = main
        self.addr = addr
        self.lock = FileLock()
        
    def get_privilege(self):# 返回用户权限
        #return random.randint(0, 15)
        return 15
    
    def get_replica(self): # 获取可用的副本
        return replica_dict
    
    def get_file_update_time(self,filename): # 获得文件最新修改时间
        if filename not in file_update_time:
            return False
        return file_update_time[filename]
    
    def replica_consistency(self,server,file,delete,content=None): # 执行保证副本一致性操作
        if delete:
            print(server,file)
            for server_tmp,addr in replica_addr_dict.items():
                if server_tmp == server:
                    continue
                else:   
                        filename = os.path.join(os.getcwd(),os.path.join(addr, file))
                        print(filename)
                        if os.path.isfile(filename):
                            os.remove(filename)
                        else:
                            shutil.rmtree(filename)  
        else:
            for server_tmp,addr in replica_addr_dict.items():
                if server_tmp == server:
                    continue
                else:
                    filename = os.path.join(os.getcwd(),os.path.join(addr, file))
                    with open(filename, 'w') as file:
                        file.write(content)
        
                        
    def list_files(self, folder=None): # 列出文件夹和文件
        try:
            if folder is None:
                folder_path = self.server_files_directory
            else:
                folder_path = os.path.join(self.server_files_directory, folder)

            files = os.listdir(folder_path)
            file_dict = {}
            # print(files)
            for file in files:
                file_path_tmp = os.path.join(folder_path, file)
                if os.path.isfile(file_path_tmp):
                    file_dict[file] = file
                elif os.path.isdir(file_path_tmp):
                    subfolder_files = self.list_files(os.path.join(folder_path, file))
                    file_dict[file] = subfolder_files

            return file_dict
        except FileNotFoundError:
            return False
    
    def upload_file(self, filename, content,updatetime): # 客户端上传文件
        filename_tmp = os.path.join(self.server_files_directory,filename)
        with open(filename_tmp, 'w') as file:
            file.write(content)
        update_file_time(filename,updatetime)
        self.replica_consistency(self.addr,filename,False,content) # 执行保证副本一致性操作
        return True
    
    def write_file(self, filename, content,updatetime): # 客户端写文件
        filename_tmp = os.path.join(self.server_files_directory,filename)
        lock_file = self.lock.acquire_lock(filename) # 请求锁 
        with open(filename_tmp, 'w') as file:
            file.write(content)
        update_file_time(filename, updatetime)
        self.replica_consistency(self.addr, filename, False, content) # 执行保证副本一致性操作
        self.lock.release_lock(lock_file)# 释放锁
        return True
    
    def download_file(self, filename):# 客户端下载文件
        filename_tmp = os.path.join(self.server_files_directory,filename)
        try:
            with open(filename_tmp, 'r') as file:
                content = file.read()
            return file_update_time[filename],content
        except FileNotFoundError:
            return False,False

    
    def delete_file(self, filename):# 客户端删除文件
        print(os.getcwd())
        filename_tmp = os.path.join(self.server_files_directory,filename)
        try:
            # 尝试删除文件
            os.remove(filename_tmp)
            self.replica_consistency(self.addr,filename,True) # 执行保证副本一致性操作
            return True
        except FileNotFoundError:
            return False  # 文件不存在时返回 False
        
    def delete_folder(self, foldername): # 客户端删除文件夹
        foldername_tmp = os.path.join(self.server_files_directory,foldername)
        try:
            # 尝试删除文件夹及其内容
            shutil.rmtree(foldername_tmp)
            self.replica_consistency(self.addr,foldername,True)# 执行保证副本一致性操作
            return True
        except FileNotFoundError:
            return False  # 文件夹不存在时返回 False
        
    def read_file(self, filename): # 客户端读文件
        filename_tmp = os.path.join(self.server_files_directory,filename)
        
        try:
            with open(filename_tmp, 'r') as file:
                content = file.read()
            return file_update_time[filename],content
        except FileNotFoundError:
            return False,False
        
def run_server(server, host, port,addr,main):
    with server((host, port), requestHandler=RequestHandler) as server_instance:
        server_instance.register_introspection_functions()
        # 注册文件服务
        file_service = FileService(addr,main)
        server_instance.register_instance(file_service)
        # 运行服务器的主循环
        print(f"Server is listening on {host}:{port}")
        server_instance.serve_forever()

def init_file_time(folder=None,indent=0): # 初始化记录文件修改时间的字典
    if folder is None:
        folder_path = os.path.join(os.getcwd(),'server1')
    else:
        folder_path = os.path.join(os.path.join(os.getcwd(),'server1'),folder)
        
    files = os.listdir(folder_path)
    for file in files:
        file_path_tmp = os.path.join(folder_path, file)
        if os.path.isfile(file_path_tmp):
            file_update_time[os.path.join(folder,file)] = time.time()
        elif os.path.isdir(file_path_tmp):
            init_file_time(os.path.join(folder, file))

def display_file_time(): # 打印文件最新修改时间
    for file,time in file_update_time.items():
        print("FIle: ",file,"Update time:",time)

def update_file_time(file,updatetime): # 修改文件最新修改时间
    file_update_time[file] = updatetime
    
def delete_file_time(file): # 删除文件修改时间
    file_update_time.pop(file)
    
if __name__ == "__main__":
    
    replica_dict = {'server1':8001,'server2':8002} # 设置副本端口号
    replica_addr_dict = {'server1':'server1','server2':'server2'} # 设置副本文件夹
    
    init_file_time("") # 初始化记录文件修改时间的字典
    display_file_time()
    
    # 创建主服务器
    main_server_thread = threading.Thread(target=run_server, args=(SimpleXMLRPCServer, 'localhost', 8000,"",True))
    main_server_thread.start()

    # 创建副本服务器1
    replica1_thread = threading.Thread(target=run_server, args=(SimpleXMLRPCServer, 'localhost', 8001,"server1",False))
    replica1_thread.start()

    # 创建副本服务器2
    replica2_thread = threading.Thread(target=run_server, args=(SimpleXMLRPCServer, 'localhost', 8002,"server2",False))
    replica2_thread.start()

    # 等待所有线程完成
    main_server_thread.join()
    replica1_thread.join()
    replica2_thread.join()