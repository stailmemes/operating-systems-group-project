<html>
<head>
<title>Repl.py</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style type="text/css">
.s0 { color: #5c6370;}
.s1 { color: #bbbbbb;}
.s2 { color: #d55fde;}
.s3 { color: #89ca78;}
.s4 { color: #2bbac5;}
.s5 { color: #d19a66;}
</style>
</head>
<body bgcolor="#282c34">
<table CELLSPACING=0 CELLPADDING=5 COLS=1 WIDTH="100%" BGCOLOR="#606060" >
<tr><td><center>
<font face="Arial, Helvetica" color="#000000">
Repl.py</font>
</center></td></tr></table>
<pre><span class="s0"># Repl.py  — combined REPL with built-ins (argparser) + externals</span>
<span class="s2">import </span><span class="s1">os, shlex, sys</span>

<span class="s2">import </span><span class="s1">commands </span><span class="s2">as </span><span class="s1">com</span>
<span class="s2">import </span><span class="s1">argparser</span>
<span class="s2">import </span><span class="s1">PrintFormatter </span><span class="s2">as </span><span class="s1">PF</span>
<span class="s2">import </span><span class="s1">keyboard</span>

<span class="s0"># externals + output helpers</span>
<span class="s2">from </span><span class="s1">external_runner </span><span class="s2">import </span><span class="s1">run_external            </span><span class="s0"># (code/exit/stdout/stderr)</span>
<span class="s0">#from output_utils   import write_stdout, write_stderr, report_exit</span>

<span class="s0"># List of built-in command names you expose via argparser.py</span>
<span class="s0"># Keep this in sync with argparser.build_parser()</span>
<span class="s1">BUILTINS = {</span>
    <span class="s3">&quot;ls&quot;</span><span class="s1">, </span><span class="s3">&quot;cd&quot;</span><span class="s1">, </span><span class="s3">&quot;pwd&quot;</span><span class="s1">, </span><span class="s3">&quot;exit&quot;</span><span class="s1">, </span><span class="s3">&quot;echo&quot;</span><span class="s1">, </span><span class="s3">&quot;cp&quot;</span><span class="s1">, </span><span class="s3">&quot;mv&quot;</span><span class="s1">, </span><span class="s3">&quot;rm&quot;</span><span class="s1">,</span>
    <span class="s3">&quot;mkdir&quot;</span><span class="s1">, </span><span class="s3">&quot;touch&quot;</span><span class="s1">, </span><span class="s3">&quot;run&quot;</span><span class="s1">, </span><span class="s3">&quot;help&quot;</span>
<span class="s1">}</span>

<span class="s2">def </span><span class="s1">prompt() -&gt; str:</span>
    <span class="s2">return </span><span class="s3">f&quot;myossh:</span><span class="s4">{</span><span class="s1">os.getcwd()</span><span class="s4">}</span><span class="s3">&gt; &quot;</span>

<span class="s2">def </span><span class="s1">Repl_loop():</span>
    <span class="s1">parses = argparser.build_parser()</span>
    <span class="s1">last_status = </span><span class="s5">0</span>
    <span class="s1">inputs =[]</span>
    <span class="s2">while True</span><span class="s1">:</span>
        <span class="s2">try</span><span class="s1">:</span>
            
            <span class="s1">line = PF.CInput(prompt())</span>
            <span class="s2">if </span><span class="s1">keyboard.is_pressed(</span><span class="s3">'up'</span><span class="s1">):</span>
                <span class="s1">print(</span><span class="s3">&quot;ello&quot;</span><span class="s1">)</span>
        <span class="s2">except </span><span class="s1">EOFError:                </span>
            <span class="s1">print()</span>
            <span class="s2">break</span>
        <span class="s2">except </span><span class="s1">KeyboardInterrupt:       </span>
            <span class="s1">print()</span>
            <span class="s2">continue</span>

        <span class="s2">if not </span><span class="s1">line </span><span class="s2">or not </span><span class="s1">line.strip():</span>
            <span class="s2">continue</span>

        <span class="s0"># tokenize</span>
        <span class="s2">try</span><span class="s1">:</span>
            <span class="s1">argv = shlex.split(line)</span>
        <span class="s2">except </span><span class="s1">ValueError </span><span class="s2">as </span><span class="s1">e:</span>
            <span class="s1">PF.errorPrint(</span><span class="s3">f&quot;parse error: </span><span class="s4">{</span><span class="s1">e</span><span class="s4">}</span><span class="s3">&quot;</span><span class="s1">)</span>
            <span class="s2">continue</span>

        <span class="s1">cmd = argv[</span><span class="s5">0</span><span class="s1">]</span>

        <span class="s0"># ---------- built-ins from argparse ----------</span>
        <span class="s2">if </span><span class="s1">cmd </span><span class="s2">in </span><span class="s1">BUILTINS:</span>
            <span class="s2">try</span><span class="s1">:</span>
                <span class="s1">args = parses.parse_args(argv)</span>
                <span class="s2">if </span><span class="s1">hasattr(args, </span><span class="s3">&quot;func&quot;</span><span class="s1">):</span>
                    <span class="s1">args.func(args)     </span><span class="s0"># dispatch to commands.py</span>
                <span class="s2">else</span><span class="s1">:</span>
                    <span class="s1">PF.errorPrint(</span><span class="s3">&quot;Unknown command!&quot;</span><span class="s1">)</span>
            <span class="s2">except </span><span class="s1">SystemExit:</span>
                <span class="s0"># argparse threw Keep REPL going</span>
                <span class="s2">continue</span>
            <span class="s2">except </span><span class="s1">Exception </span><span class="s2">as </span><span class="s1">e:</span>
                <span class="s1">PF.errorPrint(</span><span class="s3">f&quot;builtin error: </span><span class="s4">{</span><span class="s1">e</span><span class="s4">}</span><span class="s3">&quot;</span><span class="s1">)</span>
            <span class="s2">continue</span>

        <span class="s0"># ---------- external command path ----------</span>
        <span class="s1">code, out, err = run_external(argv, capture=</span><span class="s2">True</span><span class="s1">)</span>
        <span class="s1">write_stdout(out)               </span><span class="s0"># normal output</span>
        <span class="s1">write_stderr(err)               </span><span class="s0"># error output</span>
        <span class="s1">last_status = code              </span><span class="s0"># available if you want in the prompt</span>
        <span class="s0"># report_exit                   # uncomment if you want &quot;[exit N]&quot; after each run</span>

<span class="s2">if </span><span class="s1">__name__ == </span><span class="s3">&quot;__main__&quot;</span><span class="s1">:</span>
    <span class="s1">Repl_loop()</span>
</pre>
</body>
</html>