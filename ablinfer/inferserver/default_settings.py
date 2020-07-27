MODEL_PATH = "/etc/inferserver/models" ## Directory to look for model JSON files in
SESSION_PATH = "/var/inferserver"      ## Directory to store sessions in *MUST BE WRITABLE*
CLEANUP_TIMER = 300                    ## Timer in between running session cleanup, in seconds
CLEANUP_FINISHED = True                ## Cleanup finished inferences?
CLEANUP_FILES = False                  ## Remove cleaned sessions from the disk?
CLEANUP_SECONDS = 3600                 ## Number of seconds before a session is considered inactive
CHECK_INPUT_FILETYPES = True           ## Verify input file types before dispatching
WORKER_THREADS = 1                     ## Number of simultaneous inferences that can be run
