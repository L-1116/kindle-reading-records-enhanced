/* Passive evdev multiplexer, replacing the shell owner guard (not adding a
 * resident process). Lua remains the sole activity/accounting decoder.
 * No grabs, writes to input devices, power requests or periodic wakeups. */
#define _GNU_SOURCE
#ifdef IDLE_INPUT_HOST_TEST
#include "../../tests/idle_input_host.h"
#else
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/inotify.h>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <linux/input.h>
#include <poll.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#endif

#define NINPUT 64
#define BIT(a,n) (((a)[(n)/8] >> ((n)%8)) & 1)
static volatile sig_atomic_t stopped, child_done;
static int output=-1, notify=-1;
static pid_t child=-1;
static struct { int fd; dev_t dev; ino_t ino; } inputs[NINPUT];
static const char *devroot;
static void interrupted(int sig) { if(sig==SIGCHLD) child_done=1; else stopped=1; }
static int emit(const void *data, size_t len) {
    /* Each packet is below PIPE_BUF. Never block parent-death handling behind
     * a dead/stuck decoder, and fail safely instead of dropping input. */
    ssize_t n;
    do { n=write(output,data,len); } while(n<0 && errno==EINTR && !stopped && !child_done);
    return n==(ssize_t)len ? 0 : -1;
}
static int attach(const char *path, int touch) {
    struct stat st; unsigned char keys[(KEY_MAX+8)/8]={0};
    int fd=open(path,O_RDONLY|O_NONBLOCK|O_CLOEXEC), slot=touch?0:1;
    if(fd<0) return touch ? -1 : 0;
    if(fstat(fd,&st)<0 || !S_ISCHR(st.st_mode)) { close(fd); return touch ? -1 : 0; }
    for(int i=0;i<NINPUT;i++) if(inputs[i].fd>=0 && inputs[i].dev==st.st_rdev && inputs[i].ino==st.st_ino) { close(fd); return 0; }
    if(!touch && (ioctl(fd,EVIOCGBIT(EV_KEY,sizeof keys),keys)<0 || (!BIT(keys,KEY_PAGEUP) && !BIT(keys,KEY_PAGEDOWN)))) { close(fd); return 0; }
    while(slot<NINPUT && inputs[slot].fd>=0) slot++;
    if(slot==NINPUT) { close(fd); return -1; }
    if(!touch) {
        unsigned char reset=(unsigned char)(128+slot);
        if(emit(&reset,1)<0) { close(fd); return -1; }
    }
    inputs[slot].fd=fd; inputs[slot].dev=st.st_rdev; inputs[slot].ino=st.st_ino;
    char name[128]={0}; ioctl(fd,EVIOCGNAME(sizeof name),name);
    name[sizeof name-1]=0;
    fprintf(stderr,"idle_input source=%d path=%s name=%s role=%s\n",slot,path,name,touch?"touch":"page_keys_104_109");
    return 0;
}
static int scan(void) {
    DIR *d=opendir(devroot); struct dirent *e; char path[1024];
    if(!d) return -1;
    int rc=0;
    while((e=readdir(d))) {
        unsigned n; char extra;
        if(sscanf(e->d_name,"event%u%c",&n,&extra)!=1) continue;
        if(snprintf(path,sizeof path,"%s/%s",devroot,e->d_name)>=(int)sizeof path || attach(path,0)<0) { rc=-1; break; }
    }
    closedir(d); return rc;
}
static int record_child(const char *dir) {
    char path[1024], line[4096];
    snprintf(path,sizeof path,"/proc/%ld/stat",(long)child);
    FILE *f=fopen(path,"r");
    if(!f) return -1;
    char *ok=fgets(line,sizeof line,f); fclose(f);
    char *p=ok?strrchr(line,')'):NULL;
    if(!p) return -1;
    p+=2;
    for(int field=3;field<22;field++) { p=strchr(p,' '); if(!p) return -1; p++; }
    unsigned long long birth=strtoull(p,NULL,10);
    snprintf(path,sizeof path,"%s/listener.pid",dir); f=fopen(path,"w");
    if(!f) return -1;
    fprintf(f,"%ld %llu\n",(long)child,birth); return fclose(f);
}
static void remove_session(const char *dir) {
    const char *files[]={"snapshot","snapshot.new","touch-last.log","events","probe","error","owner-pipe","listener.pid",NULL};
    char path[1024];
    for(int i=0;files[i];i++) { snprintf(path,sizeof path,"%s/%s",dir,files[i]); unlink(path); }
    rmdir(dir);
}
int main(int argc,char **argv) {
    if(argc!=7) return 2; /* session, lua, decoder, touch, epoch, timeout */
    int pipefd[2], owner_gone=0, rc=2; char snapshot[1024], size[16];
    for(int i=0;i<NINPUT;i++) inputs[i].fd=-1;
    devroot=getenv("READING_INPUT_DEV"); if(!devroot) devroot="/dev/input";
    struct sigaction sa={0}; sa.sa_handler=interrupted; sigemptyset(&sa.sa_mask);
    sigaction(SIGTERM,&sa,NULL); sigaction(SIGINT,&sa,NULL); sigaction(SIGHUP,&sa,NULL); sigaction(SIGCHLD,&sa,NULL);
    signal(SIGPIPE,SIG_IGN);
    sigset_t blocked, previous; sigemptyset(&blocked);
    sigaddset(&blocked,SIGTERM); sigaddset(&blocked,SIGINT); sigaddset(&blocked,SIGHUP); sigaddset(&blocked,SIGCHLD);
    sigprocmask(SIG_BLOCK,&blocked,&previous);
    /* fd 8 is the existing owner FIFO, already opened by the daemon. */
    if(fcntl(8,F_GETFD)<0 || pipe2(pipefd,O_CLOEXEC)<0) goto done;
    snprintf(snapshot,sizeof snapshot,"%s/snapshot",argv[1]);
    snprintf(size,sizeof size,"%u",(unsigned)sizeof(struct input_event));
    pid_t guard_pid=getpid(); child=fork();
    if(child==0) {
        /* Also cover guard SIGKILL in the fork -> listener.pid window. */
        if(prctl(PR_SET_PDEATHSIG,SIGTERM)<0 || getppid()!=guard_pid) _exit(2);
        /* A TERM arriving before exec must terminate, rather than run the
         * parent's handler and leave a blocked decoder behind. */
        signal(SIGTERM,SIG_DFL); signal(SIGINT,SIG_DFL); signal(SIGHUP,SIG_DFL);
        signal(SIGCHLD,SIG_DFL); signal(SIGPIPE,SIG_DFL);
        sigprocmask(SIG_SETMASK,&previous,NULL);
        close(8); close(pipefd[1]);
        if(dup2(pipefd[0],STDIN_FILENO)<0) _exit(2);
        if(fcntl(STDIN_FILENO,F_SETFD,0)<0) _exit(2);
        if(pipefd[0]!=STDIN_FILENO) close(pipefd[0]);
        execl(argv[2],argv[2],argv[3],"-",size,snapshot,argv[5],argv[6],"--multiplex",(char*)NULL);
        _exit(127);
    }
    close(pipefd[0]); output=pipefd[1];
    if(child<0 || fcntl(output,F_SETFL,O_NONBLOCK)<0 || record_child(argv[1])<0) goto done;
    notify=inotify_init1(IN_NONBLOCK|IN_CLOEXEC);
    if(notify<0 || inotify_add_watch(notify,devroot,IN_CREATE|IN_MOVED_TO|IN_ATTRIB|IN_DELETE|IN_MOVED_FROM)<0) goto done;
    if(attach(argv[4],1)<0 || scan()<0) goto done;
    while(!stopped && !child_done) {
        struct pollfd p[NINPUT+2]; p[0]=(struct pollfd){8,POLLIN,0}; p[1]=(struct pollfd){notify,POLLIN,0};
        for(int i=0;i<NINPUT;i++) p[i+2]=(struct pollfd){inputs[i].fd,POLLIN,0};
        /* Atomic unmask + wait prevents a child-exit/TERM lost-wakeup race. */
        int n=ppoll(p,NINPUT+2,NULL,&previous);
        if(n<0) { if(errno==EINTR) continue; break; }
        if(p[0].revents) { owner_gone=1; rc=0; break; }
        int rescan=0;
        for(int i=0;i<NINPUT;i++) {
            if(!p[i+2].revents) continue;
            struct input_event events[32];
            ssize_t count=read(inputs[i].fd,events,sizeof events);
            if(count<0 && (errno==EAGAIN || errno==EINTR)) continue;
            if(count<=0 || count%sizeof(struct input_event)) {
                if(i==0) goto done; /* Losing touch must use the existing fallback. */
                fprintf(stderr,"idle_input disconnected source=%d\n",i);
                close(inputs[i].fd); inputs[i].fd=-1; rescan=1; continue;
            }
            for(size_t j=0;j<(size_t)count/sizeof(struct input_event);j++) {
                /* Unrelated keys/connection events never reach the decoder. */
                if(i && !(events[j].type==EV_SYN || (events[j].type==EV_KEY && (events[j].code==KEY_PAGEUP || events[j].code==KEY_PAGEDOWN)))) continue;
                unsigned char packet[1+sizeof(struct input_event)]; packet[0]=(unsigned char)i;
                memcpy(packet+1,&events[j],sizeof events[j]);
                if(emit(packet,sizeof packet)<0) goto done;
            }
        }
        if(p[1].revents) {
            char buffer[4096]; ssize_t nread;
            while((nread=read(notify,buffer,sizeof buffer))>0) {
                for(size_t off=0;off<(size_t)nread;) {
                    struct inotify_event *ev=(void*)(buffer+off);
                    if(ev->mask&(IN_Q_OVERFLOW|IN_IGNORED|IN_UNMOUNT)) goto done;
                    off+=sizeof *ev+ev->len;
                }
            }
            rescan=1;
        }
        if(rescan && scan()<0) break;
    }
done:
    if(rc) fprintf(stderr,"idle_input stopped; foreground timing fallback (errno=%d)\n",errno);
    if(output>=0) close(output);
    if(child>0) { kill(child,SIGTERM); while(waitpid(child,NULL,0)<0 && errno==EINTR) {} }
    if(notify>=0) close(notify);
    for(int i=0;i<NINPUT;i++) if(inputs[i].fd>=0) close(inputs[i].fd);
    if(owner_gone) remove_session(argv[1]);
    return rc;
}
