from xmlrpc.client import ServerProxy
import socket
import time
import msvcrt

class Cache:#本地缓存
    def __init__(self):
        self.cache = {} # 缓存 记录文件内容 修改时间 和 上次读时间
        self.size = 2  # 缓存大小
        
    def delete_file(self,filename): # 删除缓存内指定的文件
        if filename not in self.cache:
            return 
        self.cache.pop(filename)
        
    def update_file_LRU(self,filename,content,updatetime):# 更新缓存
        if filename in self.cache :# 更新已在缓存内的文件
            self.cache[filename]=[content,updatetime,time.time()]
            return
        
        if len(self.cache)<self.size: # 缓存大小足够,直接加入
            self.cache[filename]=[content,updatetime,time.time()]
        else:# 缓存已满 利用LRU缓存更新算法更新
            min_update_time = time.time()
            min_update_file = None 
            for file,ct in self.cache.items():
                if ct[2]<min_update_time:
                    min_update_time = ct[1]
                    min_update_file = file
            self.cache.pop(min_update_file)
            self.cache[filename]=[content,updatetime,time.time()]

            
    def read_file_time(self,filename):# 获取缓存内指定文件的记录的修改时间
        if filename not in self.cache:
            return False
        
        return self.cache[filename][1]
        
    def read_file_content(self,filename):# 获取缓存内指定文件的内容
        if filename not in self.cache:
            return False
        self.cache[filename][2] = time.time()
        return self.cache[filename][0]   
    
    def show_cache(self): # 打印缓存内容
        for file,ct in self.cache.items():
            print("file:",file,"update_time:",ct[1],"read_time:",ct[2])


class FileClient: # 客户端
    def __init__(self, server_url):
        # 首先与主服务器连接
        self.server = ServerProxy(server_url)
        self.client_port = self.get_client_port()
        # 获得可用的副本服务器
        replica_dict = self.server.get_replica()
        print("Here are the services with ports:")
        for server, port in replica_dict.items():
            print(f"Server: {server}, Port: {port}")
        # 选择可用的副本服务器并进行连接
        self.replica = input("Choose the name of server you want to connect: ")
        while self.replica not in replica_dict:
            print("This server not Found.")
            self.replica  = input("Choose the name of server you want to connect: ")
        replica_port = replica_dict[self.replica]
        server_url = 'http://localhost:'+ str(replica_port) +'/RPC2'
        self.server = ServerProxy(server_url)
        # 初始化缓存
        self.filecache = Cache()
        # 获取权限
        self.privilege = self.server.get_privilege() 
                
    def check_privilege(self,command):
        if command == 'help':
            return True
        elif command.startswith('upload_file'):
            position = 1
        elif command.startswith('download_file'):
            position = 3
        elif command.startswith('delete_file'):
            position = 2
        elif command.startswith("delete_folder"):
            position = 2
        elif command.startswith("write_file"):
            position = 3
        elif command == "list_files":
            position = 0
        elif command.startswith('read_file'):
            position = 0
        elif command.startswith('port'):
            return True
        elif command.startswith('cache'):
            return True
        elif command == "exit":
           return True
        else:
            return True
        
        mask = 1 << position
        flag= (self.privilege & mask) != 0
        if flag:
            return True
        else:
            print("You don't have the privilige!")
            return False
        
    def get_client_port(self):
        # 创建一个临时套接字以获取本地端口号
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_socket.bind(('localhost', 0))
        _, port = temp_socket.getsockname()
        temp_socket.close()
        return port
    
    def list_files(self):# 列出副本服务器下的文件夹和文件
        file_dict = self.server.list_files()
        if file_dict is not False:
            print("Files and folders on the server:")
            self.print_tree(file_dict)
        else:
            print("Error: Unable to retrieve file list from the server.")
    
    def print_tree(self, file_dict, indent=0):# 打印副本服务器下的文件夹和文件
        for file, subfiles in file_dict.items():
            print("  " * indent + f"- {file}")
            if isinstance(subfiles, dict):  # 检查是否为字典 是则为文件夹 迭代打印文件夹中的文件
                self.print_tree(subfiles, indent + 1)

    def upload_file(self, filename): # 上传文件
        with open(filename, 'r') as file:
            content = file.read()
            updatetime = time.time()
            result = self.server.upload_file(filename, content,updatetime)
            self.filecache.update_file_LRU(filename,content,updatetime) # 更新缓存
        return result

    def download_file(self, filename):# 下载文件
        
        updatetime,content = self.server.download_file(filename)
        if content is not False:
            with open(filename, 'w') as file:
                file.write(content)
            self.filecache.update_file_LRU(filename,content,updatetime) # 更新缓存
            return {"success": True, "content": content}
        else:
            return {"success": False, "error": f"File '{filename}' not found on server."}

    def write_file(self, filename):# 写文件
        updatetime = time.time()
        content = input("Input the content you write:")
        result = self.server.write_file(filename,content,updatetime)
        if result is not False:
            self.filecache.update_file_LRU(filename,content,updatetime) # 更新缓存
            return {"success": True, "message": f"File '{filename}' written on server."}
        else:
            return {"success": False, "error": f"File '{filename}' not written on server ."}
        
    def delete_file(self, filename):# 删除文件
        self.filecache.delete_file(filename)
        result = self.server.delete_file(filename) # 更新缓存
        if result:
            return {"success": True, "message": f"File '{filename}' deleted from server."}
        else:
            return {"success": False, "error": f"File '{filename}' not found on server or unable to delete."}
    
    def delete_folder(self, foldername):# 删除文件夹
        result = self.server.delete_folder(foldername) # 更新缓存
        if result:
            return {"success": True, "message": f"Folder '{foldername}' deleted from server."}
        else:
            return {"success": False, "error": f"Folder '{foldername}' not found on server or unable to delete."}
    
    def read_file(self, filename): # 读文件
        # 先比较缓存内是否有 且 是否为最新修改过的  如果满足直接读缓存
        filetime = self.filecache.read_file_time(filename)
        if filetime is not False:
            update_time = self.server.get_file_update_time(filename)
            if update_time is not False and update_time <= filetime:
                content = self.filecache.read_file_content(filename)
                print("Reading from cache")
                print(f"Content of '{filename}':\n{content}")
                return
        # 没有则读服务器
        updatetime,content = self.server.read_file(filename)
        if content is not False:
            print(f"Content of '{filename}':\n{content}")
            self.filecache.update_file_LRU(filename,content,updatetime) # 更新缓存
        else:
            print(f"Error: Unable to read file '{filename}' from the server.")
    
    def help(self): # 获取命令及用法
        print("Available Commands:")
        print("1. upload_file [filename] - Upload a file to the server.")
        print("2. download_file [filename] - Download a file from the server.")
        print("3. delete_file [filename] - Delete a file on the server.")
        print("4. help() - Display available commands.")
        print("5. exit() - Exit the client.")
        print("6. list_files(): - List files in the server folder.")
        print("7. delete_folder [foldername]: - Delete a folder on the server.")
        print("8. read_files [file_name]: - Read a file to the server.")
        print("9. port : - Display the port of the client.")
        print("10. cache : - Display the cache of the client.")
        print("11. write : - write a file from the server.")
        
    def handle(self): # 处理输入的命令
        while True:
            command = input("Enter a command (Type 'help' for available commands): ")
            
            # 检测权限
            if self.check_privilege(command) is False:
                continue
            
            if command == 'help':
                self.help()
            elif command.startswith('upload_file'):
                _, filename = command.split(' ')
                result = self.upload_file(filename)
                print(result)
            elif command.startswith('download_file'):
                _, filename = command.split(' ')
                result = self.download_file(filename)
                print(result)
            elif command.startswith('delete_file'):
                _, filename = command.split(' ')
                result = self.delete_file(filename)
                print(result)
            elif command.startswith("delete_folder"):
                _, foldername = command.split(" ", 1)
                result = self.delete_folder(foldername)
                print(result)
            elif command.startswith("write_file"):
                _, filename = command.split(" ", 1)
                result = self.write_file(filename)
                print(result)
            elif command == "list_files":
                self.list_files()
            elif command.startswith('read_file'):
                _, filename = command.split(' ')
                self.read_file(filename)
            elif command.startswith('port'):
               print(f"Client's local port: {self.client_port}")
               break
            elif command.startswith('cache'):
                self.filecache.show_cache()
            elif command == "exit":
                print("Exiting the client.")
                break
            else:
                print("Invalid command. Type 'help' for available commands.")
     
if __name__ == "__main__":
    
    client = FileClient('http://localhost:8000/RPC2')
    client.handle()


