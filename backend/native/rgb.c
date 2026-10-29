/* Typed RGB operations for custom firmware9002 only. No firmware/loader API.
 * --status uses cached properties, --probe is a read-only Feature handshake.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hid/IOHIDManager.h>
#include <IOKit/hid/IOHIDKeys.h>
#include <IOKit/IOKitLib.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>
#include "rgb_descriptor.h"
struct operation {uint8_t body[8];};
struct request {struct operation ops[70];unsigned count;int cached,probe;uint64_t expected_device;};
static struct {uint8_t report[8];CFIndex length;IOReturn error;unsigned accepted,submitted,get_calls;int last_was_set,initial_active,initial_status_valid;double deadline;} io;
static double now(void) {struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return -1;return(double)t.tv_sec+(double)t.tv_nsec/1e9;}
static int decimal(const char *text,unsigned maximum,unsigned *out) {
    if(!text || !*text || strlen(text)>3)return 0;
    unsigned n=0;for(const char *p=text;*p;++p){if(*p<'0'||*p>'9')return 0;n=n*10+(unsigned)(*p-'0');}
    if(n>maximum)return 0;*out=n;return 1;
}
static int hex_digit(char ch) {if(ch>='0'&&ch<='9')return ch-'0';if(ch>='a'&&ch<='f')return ch-'a'+10;if(ch>='A'&&ch<='F')return ch-'A'+10;return -1;}
static int parse_request_inner(int argc,char **argv,struct request *r) {
    memset(r,0,sizeof(*r));
    if(argc==2 && !strcmp(argv[1],"--status")){r->cached=1;return 1;}
    if(argc==2 && !strcmp(argv[1],"--probe")){r->probe=1;return 1;}
    if(argc==2 && !strcmp(argv[1],"--release")){r->ops[0].body[0]=0xd1;r->ops[0].body[1]=3;r->count=1;return 1;}
    if(argc==7 && !strcmp(argv[1],"--pixel")) {
        unsigned values[5];for(unsigned i=0;i<5;++i)if(!decimal(argv[i+2],i==0?4:i==1?13:255,&values[i]))return 0;
        r->ops[0].body[0]=0xd1;r->ops[0].body[1]=1;
        for(unsigned i=0;i<5;++i)r->ops[0].body[i+2]=(uint8_t)values[i];r->count=1;return 1;
    }
    if(argc==5 && !strcmp(argv[1],"--fill")) {
        unsigned values[3];for(unsigned i=0;i<3;++i)if(!decimal(argv[i+2],255,&values[i]))return 0;
        r->ops[0].body[0]=0xd1;r->ops[0].body[1]=2;
        for(unsigned i=0;i<3;++i)r->ops[0].body[i+4]=(uint8_t)values[i];r->count=1;return 1;
    }
    if(argc==3 && !strcmp(argv[1],"--batch")) {
        size_t n=strlen(argv[2]);if(!n || n>700 || n%10)return 0;
        uint8_t seen[70]={0};r->count=(unsigned)n/10;
        for(unsigned i=0;i<r->count;++i) {
            uint8_t values[5];
            for(unsigned j=0;j<5;++j) {int hi=hex_digit(argv[2][i*10+j*2]),lo=hex_digit(argv[2][i*10+j*2+1]);if(hi<0||lo<0)return 0;values[j]=(uint8_t)(hi*16+lo);}
            if(values[0]>=5 || values[1]>=14 || seen[values[0]*14+values[1]]++)return 0;
            r->ops[i].body[0]=0xd1;r->ops[i].body[1]=1;memcpy(r->ops[i].body+2,values,5);
        }
        return 1;
    }
    return 0;
}
static int parse_request(int argc,char **argv,struct request *r) {
    uint64_t expected=0;
    if(argc>=3 && !strcmp(argv[1],"--device")) {
        const char *text=argv[2];if(!*text||strlen(text)>20)return 0;
        for(const char *p=text;*p;++p)if(*p<'0'||*p>'9')return 0;
        errno=0;unsigned long long value=strtoull(text,NULL,10);if(errno||!value)return 0;
        expected=(uint64_t)value;argc-=2;argv+=2;
    }
    if(!parse_request_inner(argc,argv,r))return 0;r->expected_device=expected;return 1;
}
static int number_is(IOHIDDeviceRef d,CFStringRef key,int wanted) {
    CFTypeRef p=IOHIDDeviceGetProperty(d,key);int n=0;
    return p && CFGetTypeID(p)==CFNumberGetTypeID() && CFNumberGetValue((CFNumberRef)p,kCFNumberIntType,&n) && n==wanted;
}
static int compatible(IOHIDDeviceRef d) {
    CFTypeRef p=IOHIDDeviceGetProperty(d,CFSTR(kIOHIDReportDescriptorKey));
    return number_is(d,CFSTR(kIOHIDVendorIDKey),0x3233) && number_is(d,CFSTR(kIOHIDProductIDKey),0x6301)
        && number_is(d,CFSTR(kIOHIDVersionNumberKey),0x9002) && number_is(d,CFSTR(kIOHIDMaxFeatureReportSizeKey),8)
        && ((number_is(d,CFSTR(kIOHIDPrimaryUsagePageKey),0xff00)&&number_is(d,CFSTR(kIOHIDPrimaryUsageKey),1))
         || (number_is(d,CFSTR(kIOHIDPrimaryUsagePageKey),1)&&number_is(d,CFSTR(kIOHIDPrimaryUsageKey),6)))
        && p && CFGetTypeID(p)==CFDataGetTypeID() && CFDataGetLength((CFDataRef)p)==sizeof(rgb_descriptor)
        && !memcmp(CFDataGetBytePtr((CFDataRef)p),rgb_descriptor,sizeof(rgb_descriptor));
}
static int status_valid(const uint8_t b[8]) {return !memcmp(b,"DRGB",4)&&b[4]==1&&b[5]<=1&&b[6]<=1&&b[7]<=1;}
static int exchange(IOHIDDeviceRef d,const uint8_t *body) {
    if(!compatible(d) || now()<0 || now()>=io.deadline){io.error=kIOReturnTimeout;return 0;}
    /* Allow the prior control status/IRQ to retire before the next SETUP. */
    struct timespec settle={0,10000000};nanosleep(&settle,NULL);
    io.length=8;io.last_was_set=body!=NULL;io.error=kIOReturnSuccess;
    if(body)memcpy(io.report,body,8);else memset(io.report,0,8);
    IOReturn result;
    if(body){++io.submitted;result=IOHIDDeviceSetReport(d,kIOHIDReportTypeFeature,0,io.report,8);}
    else{++io.get_calls;result=IOHIDDeviceGetReport(d,kIOHIDReportTypeFeature,0,io.report,&io.length);}
    io.error=result;
    if(result!=kIOReturnSuccess)return 0;
    if(io.length!=8 || (!body&&!status_valid(io.report))){io.error=kIOReturnBadArgument;return 0;}
    return 1;
}
static int read_status(IOHIDDeviceRef d,unsigned attempts) {
    for(unsigned n=0;n<attempts;++n) {
        if(exchange(d,NULL))return 1;
        /* A stale zero-length control packet contains no status. Drain at most
           one additional known GET; never retry any colour write. */
        if(io.error==kIOReturnNoDevice)return 0;
    }
    return 0;
}
static int execute(IOHIDDeviceRef d,const struct request *r) {
    if(!read_status(d,3)||io.report[7])return 0;
    io.initial_active=io.report[5];io.initial_status_valid=1;if(r->probe)return 1;
    for(unsigned n=0;n<r->count;++n) {
        if(!exchange(d,r->ops[n].body))return 0;
        /* The device refuses the next SET while its previous command remains
           queued. Acknowledgement of the next SET therefore retires the prior
           valid command. Avoid inserting GETs between every LED write. */
        if(n)++io.accepted;
    }
    for(unsigned poll=0;poll<3;++poll) {
        if(!read_status(d,1)) {if(io.error==kIOReturnNoDevice)return 0;continue;}
        if(!io.report[7]) {
            int accepted=io.report[6]==1 && io.report[5]==(r->ops[r->count-1].body[1]==3?0:1);
            if(accepted)++io.accepted;return accepted;
        }
    }
    return 0;
}

int main(int argc,char **argv) {
    struct request r;
    if(!parse_request(argc,argv,&r)){puts("{\"ok\":false,\"error\":\"Invalid typed RGB action\"}");return 2;}
    IOHIDManagerRef manager=IOHIDManagerCreate(NULL,0);if(!manager)return 1;
    int vid=0x3233,pid=0x6301;CFNumberRef v=CFNumberCreate(NULL,kCFNumberIntType,&vid),p=CFNumberCreate(NULL,kCFNumberIntType,&pid);
    const void *keys[]={CFSTR(kIOHIDVendorIDKey),CFSTR(kIOHIDProductIDKey)},*values[]={v,p};
    CFDictionaryRef match=CFDictionaryCreate(NULL,keys,values,2,&kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
    IOHIDManagerSetDeviceMatching(manager,match);CFRelease(match);CFRelease(v);CFRelease(p);
    CFSetRef devices=IOHIDManagerCopyDevices(manager);IOHIDDeviceRef chosen=NULL;int count=0,vendor=0;
    if(devices) {
        CFIndex n=CFSetGetCount(devices);const void **list=calloc((size_t)n,sizeof(*list));
        if(n&&!list){CFRelease(devices);CFRelease(manager);return 1;}if(n)CFSetGetValues(devices,list);
        for(CFIndex i=0;i<n;++i)if(compatible((IOHIDDeviceRef)list[i])) {
            int is_vendor=number_is((IOHIDDeviceRef)list[i],CFSTR(kIOHIDPrimaryUsagePageKey),0xff00);
            if(is_vendor&&!vendor){chosen=NULL;count=0;vendor=1;}
            if(is_vendor==vendor){chosen=(IOHIDDeviceRef)list[i];++count;}
        }
        free(list);
    }
    uint64_t entry=0;if(count==1)IORegistryEntryGetRegistryEntryID(IOHIDDeviceGetService(chosen),&entry);
    if(r.expected_device && entry!=r.expected_device){chosen=NULL;count=0;}
    if(r.cached) {
        printf("{\"ok\":true,\"connected\":%s,\"matching_interfaces\":%d,\"rgb_control\":true,\"device_id\":\"%llu\",\"firmware\":\"9002\"}\n",count==1?"true":"false",count,(unsigned long long)entry);
        if(devices)CFRelease(devices);CFRelease(manager);return 0;
    }
    double start=now();int ok=0;io.deadline=start+8;
    if(start>=0 && count==1 && IOHIDDeviceOpen(chosen,0)==kIOReturnSuccess) {
        ok=execute(chosen,&r);
        IOHIDDeviceClose(chosen,0);
    }
    if(devices)CFRelease(devices);CFRelease(manager);
    if(!ok){fprintf(stderr,"RGB debug: length=%ld body=",(long)io.length);for(unsigned i=0;i<8;++i)fprintf(stderr,"%02x",io.report[i]);fputc('\n',stderr);}
    printf("{\"ok\":%s,\"submitted\":%s,\"accepted_count\":%u,\"submitted_count\":%u,\"previous_rgb_active\":%s,\"get_count\":%u,\"last_transfer\":\"%s\",\"rgb_active\":%s,\"pending\":%s,\"device_id\":\"%llu\",\"elapsed_ms\":%.1f,\"ioreturn\":\"0x%08x\",\"error\":%s}\n",ok?"true":"false",io.submitted?"true":"false",io.accepted,io.submitted,io.initial_status_valid?(io.initial_active?"true":"false"):"null",io.get_calls,io.last_was_set?"set":"get",status_valid(io.report)?(io.report[5]?"true":"false"):"null",status_valid(io.report)?(io.report[7]?"true":"false"):"null",(unsigned long long)entry,(now()-start)*1000,(unsigned)io.error,ok?"null":"\"RGB transaction failed; colour writes were not retried\"");
    return ok?0:1;
}
