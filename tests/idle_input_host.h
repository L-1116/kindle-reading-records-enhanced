/* Host syscall fixture for the production C guard. No real input/screen API. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#define ssize_t fixture_ssize_t
#define pid_t fixture_pid_t
#define dev_t fixture_dev_t
#define ino_t fixture_ino_t
#define sigset_t fixture_sigset_t
#define sig_atomic_t fixture_sig_atomic_t
typedef intptr_t ssize_t;
typedef int pid_t;
typedef unsigned dev_t;
typedef unsigned ino_t;
typedef int sigset_t;
typedef int sig_atomic_t;
struct sigaction { void (*sa_handler)(int); sigset_t sa_mask; };
struct stat { dev_t st_rdev; ino_t st_ino; int st_mode; };
struct pollfd { int fd; short events,revents; };
struct input_event { int32_t sec,usec; uint16_t type,code; int32_t value; };
struct inotify_event { int wd; uint32_t mask,cookie,len; };
struct dirent { char d_name[64]; };
typedef int DIR;
#define KEY_MAX 767
#define KEY_PAGEUP 104
#define KEY_PAGEDOWN 109
#define EV_KEY 1
#define EV_SYN 0
#define EVIOCGBIT(a,b) 1
#define EVIOCGNAME(a) 2
#define POLLIN 1
#define IN_CREATE 1
#define IN_MOVED_TO 2
#define IN_ATTRIB 4
#define IN_DELETE 8
#define IN_MOVED_FROM 16
#define IN_Q_OVERFLOW 32
#define IN_IGNORED 64
#define IN_UNMOUNT 128
#define IN_NONBLOCK 1
#define IN_CLOEXEC 2
#define O_RDONLY 0
#define O_NONBLOCK 1
#define O_CLOEXEC 2
#define F_GETFD 1
#define F_SETFL 2
#define F_SETFD 3
#define SIGCHLD 17
#define SIGTERM 15
#define SIGINT 2
#define SIG_DFL ((void (*)(int))0)
#define SIG_IGN ((void (*)(int))1)
#define SIGHUP 1
#define SIGPIPE 13
#define SIG_BLOCK 1
#define SIG_SETMASK 2
#define STDIN_FILENO 0
#define PR_SET_PDEATHSIG 1
#define S_ISCHR(x) ((x)==1)
static int phase,scenario,enumeration,hotplug,notify_read,killed,reaped,removed;
static unsigned char captured[8192]; static size_t capture_len;
static void fixture__exit(int rc) { exit(rc); }
static int fixture_open(const char *p,int flags) {
    (void)flags;
    if(strstr(p,"event0")) return 100;
    if(strstr(p,"event7")) return 107;
    if(strstr(p,"event9")) return 109;
    if(strstr(p,"event3")) return 103;
    return -1;
}
static int fixture_close(int fd) { (void)fd; return 0; }
static int fixture_fstat(int fd,struct stat *st) { st->st_mode=1; st->st_rdev=(unsigned)fd; st->st_ino=(unsigned)fd; return 0; }
static int fixture_ioctl(int fd,int op,void *buf) {
    if(op==1) {
        unsigned char *bits=buf;
        int code=fd==109?115:fd==103?109:104; /* volume-only event9 is excluded */
        bits[code/8]|=(unsigned char)(1u<<(code%8));
    } else strcpy(buf,fd==107?"kindle-input-pt":"fixture");
    return 0;
}
static ssize_t fixture_write(int fd,const void *data,size_t n) {
    assert(fd==201);
    if(scenario==4) { errno=EAGAIN; return -1; }
    assert(capture_len+n<=sizeof captured); memcpy(captured+capture_len,data,n); capture_len+=n;
    return (ssize_t)n;
}
static DIR *fixture_opendir(const char *p) { static DIR d; (void)p; enumeration=0; return &d; }
static struct dirent *fixture_readdir(DIR *d) {
    static struct dirent ent; (void)d;
    const char *names[]={".","event0","event7","event9",hotplug?"event3":NULL,NULL};
    const char *s=names[enumeration++]; if(!s) return NULL;
    strcpy(ent.d_name,s); return &ent;
}
static int fixture_closedir(DIR *d) { (void)d; return 0; }
static int fixture_fcntl(int fd,int op,...) { (void)fd;(void)op; return 0; }
static int fixture_sigemptyset(sigset_t *s) { *s=0; return 0; }
static int fixture_sigaddset(sigset_t *s,int n) { (void)s;(void)n; return 0; }
static int fixture_sigprocmask(int op,const sigset_t *s,sigset_t *out) { (void)op;(void)s;if(out)*out=0;return 0; }
static int fixture_sigaction(int sig,const struct sigaction *sa,void *old) { (void)sig;(void)sa;(void)old;return 0; }
static void (*fixture_signal(int sig,void (*handler)(int)))(int) { (void)sig;return handler; }
static int fixture_pipe2(int f[2],int flags) { (void)flags;f[0]=200;f[1]=201;return 0; }
static pid_t fixture_fork(void) { return 123; }
static pid_t fixture_getpid(void) { return 122; }
static pid_t fixture_getppid(void) { return 122; }
static int fixture_prctl(int op,int sig) { assert(op==PR_SET_PDEATHSIG && sig==SIGTERM);return 0; }
static int fixture_dup2(int a,int b) { (void)a;(void)b;return 0; }
static int fixture_execl(const char *p,...) { (void)p; return -1; }
static int fixture_inotify_init1(int flags) { (void)flags;return 202; }
static int fixture_inotify_add_watch(int fd,const char *p,int mask) { (void)fd;(void)p;(void)mask;return scenario==5?-1:1; }
static ssize_t fixture_read(int fd,void *buf,size_t n) {
    if(fd==202) {
        if(notify_read++) { errno=EAGAIN;return -1; }
        struct inotify_event ev={0,IN_CREATE,0,0}; assert(n>=sizeof ev);memcpy(buf,&ev,sizeof ev);return sizeof ev;
    }
    if(scenario==3) { errno=ENODEV;return -1; }
    struct input_event e[4]={{1001+phase,0,EV_KEY,fd==100?330:fd==103?109:104,1},
                              {1001+phase,0,EV_SYN,0,0},
                              {1001+phase,0,EV_KEY,115,1},
                              {1001+phase,0,EV_SYN,0,0}};
    size_t size=fd==107?sizeof e:2*sizeof *e;
    assert(n>=size); memcpy(buf,e,size);return (ssize_t)size;
}
/* The production signal handler/global flag are defined after this header. */
static int fixture_ppoll(struct pollfd *p,int n,const void *timeout,const sigset_t *mask);
static FILE *fixture_fopen(const char *p,const char *m) {
    if(strstr(p,"/proc/123/stat")) {
        FILE *f=tmpfile(); assert(f);
        fputs("123 (lua worker) S 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 456 0\n",f); rewind(f);return f;
    }
    return fopen(p,m);
}
static int fixture_kill(pid_t pid,int sig) { assert(pid==123 && sig==SIGTERM); killed++;return 0; }
static pid_t fixture_waitpid(pid_t pid,void *status,int flags) { (void)status;(void)flags;assert(pid==123);reaped++;return pid; }
static int fixture_unlink(const char *p) { (void)p;removed++;return 0; }
static int fixture_rmdir(const char *p) { (void)p;removed++;return 0; }
#define open fixture_open
#define close fixture_close
#define fstat fixture_fstat
#define ioctl fixture_ioctl
#define write fixture_write
#define opendir fixture_opendir
#define readdir fixture_readdir
#define closedir fixture_closedir
#define fcntl fixture_fcntl
#define sigemptyset fixture_sigemptyset
#define sigaddset fixture_sigaddset
#define sigprocmask fixture_sigprocmask
#define sigaction(...) fixture_sigaction(__VA_ARGS__)
#define signal fixture_signal
#define pipe2 fixture_pipe2
#define fork fixture_fork
#define getpid fixture_getpid
#define getppid fixture_getppid
#define prctl fixture_prctl
#define dup2 fixture_dup2
#define execl fixture_execl
#define _exit fixture__exit
#define inotify_init1 fixture_inotify_init1
#define inotify_add_watch fixture_inotify_add_watch
#define read fixture_read
#define ppoll fixture_ppoll
#define fopen fixture_fopen
#define kill fixture_kill
#define waitpid fixture_waitpid
#define unlink fixture_unlink
#define rmdir fixture_rmdir
