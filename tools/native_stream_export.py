"""Bounded street export patch for separately installed AGPL-3.0 TexasSolver.

Generated native adaptations retain the backend's AGPL-3.0 license. Original
sources are untouched. Training, isomorphism and probabilities are unchanged;
completed chance subtrees are serialized and released instead of accumulated.
"""
from pathlib import Path
import hashlib


def patch_stream_export(root, out, sources, console_text):
    console_anchor = '}else if(command == "dump_result"){'
    if console_text.count(console_anchor) != 1:
        raise ValueError('STREAM_UNSUPPORTED_CONSOLE')
    console_text = console_text.replace(console_anchor,
        '}else if(command == "dump_result_stream"){\n'
        '        this->ps.dump_strategy(paramstr,-this->dump_rounds);\n    ' + console_anchor)
    generated = out.with_name(out.name + '.CommandLineTool.cpp')
    generated.write_text(console_text)
    pcfr = next(Path(s) for s in sources if s.endswith('.PCfrSolver.cpp'))
    text = pcfr.read_text()
    sink = r'''
#include <zlib.h>
static gzFile vp_stream_sink = nullptr;
void vp_set_stream(gzFile sink) { vp_stream_sink = sink; }
void vp_stream_record(const json& record) {
    if(!vp_stream_sink) throw runtime_error("stream sink missing");
    string line = record.dump(); line.push_back('\n');
    size_t offset = 0;
    while(offset < line.size()) {
        unsigned count = (unsigned)std::min<size_t>(line.size()-offset,1048576);
        int written = gzwrite(vp_stream_sink,line.data()+offset,count);
        if(written <= 0) throw runtime_error("stream write failed");
        offset += (size_t)written;
    }
}
'''
    text = text.replace('//#define DEBUG;',sink+'\n//#define DEBUG;',1)
    anchor = 'this->reConvertJson(childerns,dealcards,one_card_str,depth + 1,max_depth,new_prefix,new_deal,new_exchange_color_list,child_board_long);'
    if text.count(anchor) != 1:
        raise ValueError('STREAM_UNSUPPORTED_CHANCE_VISITOR')
    replacement = r'''
            if(vp_stream_sink && Card::boardsHasIntercept(current_board_long,
                    Card::boardCards2long(vector<string>{one_card_str}))) continue;
            new_prefix.back() = "Chance:" + one_card_str;
            ''' + anchor + r'''
            if(vp_stream_sink && dealcards.contains(one_card_str)) {
                json& completed = dealcards[one_card_str];
                vp_stream_record(json{{"schema","software.native-street.v1"},
                    {"path",new_prefix},{"node",completed}});
                completed = json{{"stream_ref",new_prefix}};
            }
'''
    text = text.replace(anchor,replacement)
    pcfr.write_text(text)
    original = root/'src/runtime/PokerSolver.cpp'
    runtime = original.read_text()
    old = '''    json dump_json = this->solver->dumps(false,dump_rounds);'''
    if runtime.count(old)!=1:
        raise ValueError('STREAM_UNSUPPORTED_RUNTIME')
    runtime = runtime.replace('#include "runtime/PokerSolver.h"',
        '#include "runtime/PokerSolver.h"\n#include <zlib.h>\n'
        'extern void vp_set_stream(gzFile);\nextern void vp_stream_record(const json&);')
    runtime = runtime.replace(old,r'''
    if(dump_rounds < 0) {
        gzFile file = gzopen(dump_file.c_str(),"wb1");
        if(!file) throw runtime_error("stream output could not be opened");
        vp_set_stream(file);
        try {
            json root = this->solver->dumps(false,-dump_rounds);
            vp_stream_record(json{{"schema","software.native-street.v1"},
                {"path",vector<string>{"begin"}},{"node",root},{"root",true}});
        } catch(...) {
            vp_set_stream(nullptr); gzclose(file); throw;
        }
        vp_set_stream(nullptr);
        if(gzclose(file)!=Z_OK) throw runtime_error("stream close failed");
        return;
    }
'''+old)
    changed = out.with_name(out.name+'.PokerSolver.cpp')
    changed.write_text(runtime)
    sources = [str(changed) if s==str(original) else s for s in sources]
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (pcfr,changed,generated)}
    return sources,console_text,hashes
