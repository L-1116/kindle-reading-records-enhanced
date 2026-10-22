#define IDLE_INPUT_HOST_TEST
#define main idle_guard_main
#include "../native/idle-input/idle-input.c"
#undef main

static int fixture_ppoll(struct pollfd *p,int n,const void *timeout,const sigset_t *mask) {
    (void)n;(void)mask;assert(timeout==NULL); /* no periodic polling */
    assert(phase++<10);
    if(scenario==1) { interrupted(SIGCHLD);errno=EINTR;return -1; }
    if(scenario==2) { interrupted(SIGTERM);errno=EINTR;return -1; }
    if(scenario==3) { p[2].revents=POLLIN;return 1; }
    switch(phase) {
    case 1:p[2].revents=POLLIN;break;
    case 2:p[3].revents=POLLIN;break;
    case 3:hotplug=1;p[1].revents=POLLIN;break;
    case 4:p[4].revents=POLLIN;break;
    default:p[0].revents=POLLIN;break; /* daemon SIGKILL closes FIFO */
    }
    return 1;
}
int main(int argc,char **argv) {
    assert(argc==2);
    char *args[]={"idle-input",argv[1],"fixture-lua","decoder.lua","/dev/input/event0","1000","120",NULL};
    for(scenario=0;scenario<6;scenario++) {
        phase=enumeration=hotplug=notify_read=killed=reaped=removed=0;
        stopped=child_done=0; capture_len=0; child=-1;output=notify=-1;
        assert(idle_guard_main(7,args)==(scenario==0?0:2));
        assert(killed==1 && reaped==1);
        char path[1024], line[128];snprintf(path,sizeof path,"%s/listener.pid",argv[1]);
        FILE *f=fopen(path,"r");assert(f && fgets(line,sizeof line,f));fclose(f);
        assert(strcmp(line,"123 456\n")==0); /* PID reuse protection */
        assert(removed==(scenario==0?9:0));
        if(scenario==0) {
            int touch=0,page=0,reset=0;size_t pos=0;
            while(pos<capture_len) {
                unsigned char id=captured[pos++];
                if(id>=128) { reset++;continue; }
                struct input_event ev;memcpy(&ev,captured+pos,sizeof ev);pos+=sizeof ev;
                if(id==0) touch++;
                else { assert(ev.type==EV_SYN || (ev.type==EV_KEY && (ev.code==104 || ev.code==109)));page++; }
            }
            assert(touch==2 && page==5 && reset==2);
        }
    }
    puts("native guard: PASS (multiplex, capability filter, hotplug, owner death, child exit, TERM, lost touch, backpressure, inotify failure; mocked syscalls)");
    return 0;
}
