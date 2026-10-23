/* Bounded, on-demand image preparation. No framebuffer access or shared libraries.
 * stb_image is also used by FBInk. Vendor pin/license: vendor/README.md. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <dirent.h>
#include <unistd.h>
#ifdef _WIN32
#include <windows.h>
#define O_NOFOLLOW 0
#define O_DIRECTORY 0
#define O_NONBLOCK 0
static void wide(const char *s,wchar_t *w) { MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s,-1,w,4096); }
static int uopen(const char *p,int flags,int mode) { wchar_t w[4096]={0};wide(p,w);return _wopen(w,flags|O_BINARY,mode); }
static int uunlink(const char *p){wchar_t w[4096]={0};wide(p,w);return _wunlink(w);}
static int urename(const char *a,const char *b){wchar_t x[4096]={0},y[4096]={0};wide(a,x);wide(b,y);return _wrename(x,y);}
static DWORD attrs(const char *p){wchar_t w[4096]={0};wide(p,w);return GetFileAttributesW(w);}
#define open(p,f,...) uopen(p,f,0)
#define unlink uunlink
#define rename urename
#else
#include <sys/resource.h>
#endif
#define STBI_ONLY_JPEG
#define STBI_ONLY_PNG
#define STBI_ONLY_BMP
#define STBI_ONLY_GIF
#define STBI_NO_HDR
#define STBI_NO_LINEAR
#define STBI_NO_SIMD
#define STBI_MAX_DIMENSIONS 8192
#define STB_IMAGE_IMPLEMENTATION
#include "vendor/stb_image.h"
#define MAX_FILE (8*1024*1024)
#define MAX_PIXELS (12*1024*1024)
#define W 240
#define H 360

static int safe_name(const char *s) {
    size_t n = strlen(s);
    if (!n || n>255 || !strcmp(s,".") || !strcmp(s,"..")) return 0;
    for (;*s;s++) if ((unsigned char)*s<32 || *s==127 || *s=='/' || *s=='\\') return 0;
    return 1;
}
static int is_image(const char *s) {
    const char *e=strrchr(s,'.');
    return e && (!strcasecmp(e,".jpg") || !strcasecmp(e,".jpeg") || !strcasecmp(e,".png"));
}
static int open_dir(const char *path) {
#ifdef _WIN32
    DWORD a=attrs(path);
    if (a==INVALID_FILE_ATTRIBUTES || !(a&FILE_ATTRIBUTE_DIRECTORY) || (a&FILE_ATTRIBUTE_REPARSE_POINT)) return -1;
    return _open("NUL",O_RDONLY);
#else
    return open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
#endif
}
static int child_open(int dir, const char *base, const char *name, int flags, int mode) {
    if (!safe_name(name)) return -1;
#ifdef _WIN32
    char p[4096]; (void)dir;
    if (snprintf(p,sizeof(p),"%s/%s",base,name)>=(int)sizeof(p)) return -1;
    DWORD a=attrs(p);
    if (a!=INVALID_FILE_ATTRIBUTES && (a&FILE_ATTRIBUTE_REPARSE_POINT)) return -1;
    return uopen(p,flags,mode);
#else
    (void)base; return openat(dir,name,flags|O_NOFOLLOW,mode);
#endif
}
static unsigned char *read_image(int fd, size_t *len) {
    struct stat st; unsigned char *buf;
    if (fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_size<16 || st.st_size>MAX_FILE) return NULL;
    *len=(size_t)st.st_size; buf=malloc(*len);
    if (!buf) return NULL;
    size_t n=0; ssize_t r;
    while(n<*len && (r=read(fd,buf+n,*len-n))>0) n+=(size_t)r;
    if(n!=*len){free(buf);return NULL;} return buf;
}
static int dimensions(const unsigned char *data,size_t n,int *w,int *h,int custom) {
    int c;
    if(custom && !((n>8 && !memcmp(data,"\x89PNG\r\n\x1a\n",8)) ||
                   (n>3 && data[0]==255 && data[1]==216 && data[2]==255))) return 0;
    if(n>8 && !memcmp(data,"\x89PNG\r\n\x1a\n",8) &&
       (n<12 || memcmp(data+n-12,"\0\0\0\0IEND\xae\x42\x60\x82",12))) return 0;
    if(n>3 && data[0]==255 && data[1]==216 && (data[n-2]!=255 || data[n-1]!=217)) return 0;
    return stbi_info_from_memory(data,(int)n,w,h,&c) && *w>0 && *h>0 &&
           *w<=8192 && *h<=8192 && (uint64_t)*w * *h<=MAX_PIXELS;
}
static int scan_info(int fd) {
    struct stat st;unsigned char head[16],tail[12];int w,h,c,ok=0;
    if(fstat(fd,&st) || !S_ISREG(st.st_mode) || st.st_size<16 || st.st_size>MAX_FILE || read(fd,head,16)!=16) return 0;
    if(!memcmp(head,"\x89PNG\r\n\x1a\n",8)) {
        if(lseek(fd,-12,SEEK_END)<0 || read(fd,tail,12)!=12 || memcmp(tail,"\0\0\0\0IEND\xae\x42\x60\x82",12)) return 0;
    } else if(head[0]==255 && head[1]==216 && head[2]==255) {
        if(lseek(fd,-2,SEEK_END)<0 || read(fd,tail,2)!=2 || tail[0]!=255 || tail[1]!=217)return 0;
    } else return 0;
    lseek(fd,0,SEEK_SET);FILE *f=fdopen(dup(fd),"rb");if(!f)return 0;
    ok=stbi_info_from_file(f,&w,&h,&c) && w>0 && h>0 && w<=8192 && h<=8192 && (uint64_t)w*h<=MAX_PIXELS;
    fclose(f);return ok;
}
static uint64_t hash_bytes(uint64_t h,const unsigned char *s,size_t n) {
    while(n--) { h^=*s++; h*=UINT64_C(1099511628211); } return h;
}
static int cache_format_valid(int fd,int gray) {
    char h[15]; struct stat st;
    return fd>=0 && !fstat(fd,&st) && S_ISREG(st.st_mode) &&
           st.st_size==W*H*(gray?1:3)+15 && read(fd,h,15)==15 &&
           !memcmp(h,gray?"P5\n240 360\n255\n":"P6\n240 360\n255\n",15);
}
static void prune(const char *base,const char *keep) {
    for(;;) {
    int dir=open_dir(base); if(dir<0)return;
    int count=0; time_t oldest=0;
    char victim[256]="",p[4096]; struct stat st;
#ifdef _WIN32
    wchar_t pattern[4096]={0};char pat[4096];snprintf(pat,sizeof(pat),"%s/*",base);wide(pat,pattern);
    WIN32_FIND_DATAW e;HANDLE d=FindFirstFileW(pattern,&e);
    if(d==INVALID_HANDLE_VALUE){close(dir);return;}
    do { char name[1024];WideCharToMultiByte(CP_UTF8,0,e.cFileName,-1,name,sizeof(name),NULL,NULL);
#else
    DIR *d=opendir(base); struct dirent *e;
    if(!d){close(dir);return;}
    while((e=readdir(d))) { const char *name=e->d_name;
#endif
        size_t n=strlen(name);
        if(n!=20 || (strcmp(name+16,".pgm") && strcmp(name+16,".ppm")) ||
           strspn(name,"0123456789abcdef")!=16) continue;
        int fd=child_open(dir,base,name,O_RDONLY|O_NONBLOCK,0);
        int valid=cache_format_valid(fd,!strcmp(name+16,".pgm"));
        if(valid)valid=!fstat(fd,&st);
        if(fd>=0)close(fd);
        if(!valid)continue;
        count++;
        if(!strcmp(name,keep)) continue;
        if(!victim[0] || st.st_mtime<oldest) {
            oldest=st.st_mtime; strcpy(victim,name);
        }
#ifdef _WIN32
    } while(FindNextFileW(d,&e));FindClose(d);
#else
    }
    closedir(d);
#endif
    close(dir);
    if(count<=128 || !victim[0] || snprintf(p,sizeof(p),"%s/%s",base,victim)>=(int)sizeof(p) || unlink(p)) return;
    }
}
int main(int argc,char **argv) {
#ifdef _WIN32
    _setmode(_fileno(stdout),O_BINARY);
    int count_args=0;wchar_t **wide_args=CommandLineToArgvW(GetCommandLineW(),&count_args);
    if(!wide_args)return 2;
    char **utf_args=calloc(count_args+1,sizeof(char *));if(!utf_args)return 2;
    for(int i=0;i<count_args;i++) {
        int len=WideCharToMultiByte(CP_UTF8,0,wide_args[i],-1,NULL,0,NULL,NULL);
        utf_args[i]=malloc(len);if(!utf_args[i])return 2;
        WideCharToMultiByte(CP_UTF8,0,wide_args[i],-1,utf_args[i],len,NULL,NULL);
    }
    argv=utf_args;argc=count_args;
#endif
#ifndef _WIN32
    struct rlimit mem={96*1024*1024,96*1024*1024},cpu={5,5};
    setrlimit(RLIMIT_AS,&mem); setrlimit(RLIMIT_CPU,&cpu);
#endif
    if(argc==3 && !strcmp(argv[1],"scan")) {
        int dir=open_dir(argv[2]); if(dir<0) return 1;
        int count=0;
#ifdef _WIN32
        wchar_t pattern[4096]={0};char pat[4096];snprintf(pat,sizeof(pat),"%s/*",argv[2]);wide(pat,pattern);
        WIN32_FIND_DATAW e;HANDLE d=FindFirstFileW(pattern,&e);if(d==INVALID_HANDLE_VALUE){close(dir);return 1;}
        do { char name[1024];WideCharToMultiByte(CP_UTF8,0,e.cFileName,-1,name,sizeof(name),NULL,NULL);
#else
        DIR *d=opendir(argv[2]); if(!d){close(dir);return 1;}
        struct dirent *e;
        while((e=readdir(d)) && count<4096) { const char *name=e->d_name;
#endif
            if(!safe_name(name) || !is_image(name)) continue;
            int fd=child_open(dir,argv[2],name,O_RDONLY|O_NONBLOCK,0);
            if(fd>=0 && scan_info(fd)) {puts(name);count++;}
            if(fd>=0) close(fd);
#ifdef _WIN32
        } while(count<4096 && FindNextFileW(d,&e));FindClose(d);
#else
        }
        closedir(d);
#endif
        close(dir);return 0;
    }
    /* prepare DIR FILENAME CACHE, or real PATH CACHE. Never sends user paths to FBInk. */
    int custom=argc==5 && !strcmp(argv[1],"prepare"),real=argc==4 && !strcmp(argv[1],"real");
    if(!custom && !real) return 2;
    int dir=-1,fd=-1,w,h,c;
    const char *cache=argv[custom?4:3];
    if(custom) {
        if(!safe_name(argv[3]) || !is_image(argv[3])) return 1;
        dir=open_dir(argv[2]); if(dir<0) return 1;
        fd=child_open(dir,argv[2],argv[3],O_RDONLY|O_NONBLOCK,0);close(dir);
    } else fd=open(argv[2],O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
    size_t n=0; unsigned char *data=fd>=0?read_image(fd,&n):NULL;
    if(fd>=0) close(fd);
    if(!data || !dimensions(data,n,&w,&h,custom)){free(data);return 1;}
    /* A new namespace prevents reuse of the lossy v1 grayscale previews. */
    uint64_t hash=hash_bytes(UINT64_C(14695981039346656037),(unsigned char *)"v2",2);
    hash=hash_bytes(hash,data,n);
    char name[32],tmp[64],out[4096];
    snprintf(name,sizeof(name),"%016llx.ppm",(unsigned long long)hash);
    int cd=open_dir(cache); if(cd<0){free(data);return 1;}
    fd=child_open(cd,cache,name,O_RDONLY,0);
    if(cache_format_valid(fd,0)) { close(fd);close(cd);free(data);prune(cache,name);printf("%s/%s\n",cache,name);return 0; }
    if(fd>=0)close(fd);
    unsigned char *pixels=stbi_load_from_memory(data,(int)n,&w,&h,&c,4);free(data);
    if(!pixels){close(cd);return 1;}
    unsigned char result[W*H*3];memset(result,255,sizeof(result));
    int dw=W,dh=(int)((int64_t)h*W/w);
    if(dh>H){dh=H;dw=(int)((int64_t)w*H/h);} if(dw<1)dw=1;if(dh<1)dh=1;
    for(int y=0;y<dh;y++) for(int x=0;x<dw;x++) {
        /* Composite RGBA on white before bilinear sampling, retaining RGB. */
        double sx=((x+.5)*w/dw)-.5,sy=((y+.5)*h/dh)-.5;
        if(sx<0)sx=0;if(sy<0)sy=0;
        int x0=(int)sx,y0=(int)sy,x1=x0+1<w?x0+1:x0,y1=y0+1<h?y0+1:y0;
        double fx=sx-x0,fy=sy-y0;
        int xs[4]={x0,x1,x0,x1},ys[4]={y0,y0,y1,y1};
        double weights[4]={(1-fx)*(1-fy),fx*(1-fy),(1-fx)*fy,fx*fy};
        for(int channel=0;channel<3;channel++) {
            double v=0;
            for(int k=0;k<4;k++){unsigned char *p=pixels+4*((size_t)ys[k]*w+xs[k]);v+=weights[k]*(255-(255-p[channel])*p[3]/255.0);}
            result[3*((y+(H-dh)/2)*W+x+(W-dw)/2)+channel]=(unsigned char)(v+.5);
        }
    }
    stbi_image_free(pixels);
    snprintf(tmp,sizeof(tmp),".prepare-%ld.tmp",(long)getpid());
    fd=child_open(cd,cache,tmp,O_WRONLY|O_CREAT|O_EXCL,0600);
    int ok=0;
    if(fd>=0) {
        FILE *f=fdopen(fd,"wb");
        if(f){ok=fwrite("P6\n240 360\n255\n",1,15,f)==15 && fwrite(result,1,sizeof(result),f)==sizeof(result);if(fclose(f))ok=0;}
        else close(fd);
    }
    close(cd);
    if(snprintf(out,sizeof(out),"%s/%s",cache,name)>=(int)sizeof(out))ok=0;
    char temp_path[4096];snprintf(temp_path,sizeof(temp_path),"%s/%s",cache,tmp);
    if(!ok){unlink(temp_path);return 1;}
#ifdef _WIN32
    unlink(out);
#endif
    if(rename(temp_path,out)){unlink(temp_path);return 1;}
    prune(cache,name);puts(out);return 0;
}
