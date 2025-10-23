<html>
<head>
<title>external_runner.py</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style type="text/css">
.s0 { color: #5c6370;}
.s1 { color: #bbbbbb;}
.s2 { color: #d55fde;}
.s3 { color: #d19a66;}
.s4 { color: #89ca78;}
.s5 { color: #2bbac5;}
</style>
</head>
<body bgcolor="#282c34">
<table CELLSPACING=0 CELLPADDING=5 COLS=1 WIDTH="100%" BGCOLOR="#606060" >
<tr><td><center>
<font face="Arial, Helvetica" color="#000000">
external_runner.py</font>
</center></td></tr></table>
<pre><span class="s0"># external_runner.py</span>
<span class="s2">from </span><span class="s1">__future__ </span><span class="s2">import </span><span class="s1">annotations</span>
<span class="s2">import </span><span class="s1">os, shutil, subprocess, sys</span>
<span class="s2">from </span><span class="s1">typing </span><span class="s2">import </span><span class="s1">Tuple, Optional</span>

<span class="s1">NOT_FOUND = </span><span class="s3">127     </span>
<span class="s1">NOT_EXEC  = </span><span class="s3">126    </span>

<span class="s2">def </span><span class="s1">resolve_executable(cmd: str) -&gt; Optional[str]:</span>
    <span class="s0">&quot;&quot;&quot;Return absolute path to executable or None. 
    If cmd contains '/', treat it as a direct path. Otherwise search PATH.&quot;&quot;&quot;</span>
    <span class="s2">if </span><span class="s4">&quot;/&quot; </span><span class="s2">in </span><span class="s1">cmd:</span>
        <span class="s2">return </span><span class="s1">cmd </span><span class="s2">if </span><span class="s1">os.path.exists(cmd) </span><span class="s2">else None</span>
    <span class="s2">return </span><span class="s1">shutil.which(cmd)</span>

<span class="s2">def </span><span class="s1">run_external(argv: list[str], *, capture: bool = </span><span class="s2">False</span><span class="s1">) -&gt; Tuple[int, str, str]:</span>
    <span class="s0">&quot;&quot;&quot;Run an external program. 
    Returns (exit_code, stdout_text, stderr_text). 
    If capture=False, streams directly to terminal and returns empty strings.&quot;&quot;&quot;</span>
    <span class="s1">exe = resolve_executable(argv[</span><span class="s3">0</span><span class="s1">])</span>
    <span class="s2">if not </span><span class="s1">exe:</span>
        <span class="s2">return </span><span class="s1">NOT_FOUND, </span><span class="s4">&quot;&quot;</span><span class="s1">, </span><span class="s4">f&quot;</span><span class="s5">{</span><span class="s1">argv[</span><span class="s3">0</span><span class="s1">]</span><span class="s5">}</span><span class="s4">: command not found</span><span class="s5">\n</span><span class="s4">&quot;</span>
    <span class="s2">try</span><span class="s1">:</span>
        <span class="s2">if </span><span class="s1">capture:</span>
            <span class="s1">cp = subprocess.run([exe, *argv[</span><span class="s3">1</span><span class="s1">:]], text=</span><span class="s2">True</span><span class="s1">, capture_output=</span><span class="s2">True</span><span class="s1">)</span>
            <span class="s2">return </span><span class="s1">cp.returncode, cp.stdout, cp.stderr</span>
        <span class="s2">else</span><span class="s1">:</span>
            <span class="s1">cp = subprocess.run([exe, *argv[</span><span class="s3">1</span><span class="s1">:]])</span>
            <span class="s2">return </span><span class="s1">cp.returncode, </span><span class="s4">&quot;&quot;</span><span class="s1">, </span><span class="s4">&quot;&quot;</span>
    <span class="s2">except </span><span class="s1">PermissionError:</span>
        <span class="s2">return </span><span class="s1">NOT_EXEC, </span><span class="s4">&quot;&quot;</span><span class="s1">, </span><span class="s4">f&quot;</span><span class="s5">{</span><span class="s1">argv[</span><span class="s3">0</span><span class="s1">]</span><span class="s5">}</span><span class="s4">: permission denied</span><span class="s5">\n</span><span class="s4">&quot;</span>
    <span class="s2">except </span><span class="s1">FileNotFoundError:</span>
        <span class="s2">return </span><span class="s1">NOT_FOUND, </span><span class="s4">&quot;&quot;</span><span class="s1">, </span><span class="s4">f&quot;</span><span class="s5">{</span><span class="s1">argv[</span><span class="s3">0</span><span class="s1">]</span><span class="s5">}</span><span class="s4">: no such file or directory</span><span class="s5">\n</span><span class="s4">&quot;</span>

<span class="s0">#Background hook to add soon</span>
<span class="s2">def </span><span class="s1">start_background(argv: list[str]) -&gt; subprocess.Popen:</span>
    <span class="s0">&quot;&quot;&quot;Non-blocking run; caller manages job table &amp; output.&quot;&quot;&quot;</span>
    <span class="s1">exe = resolve_executable(argv[</span><span class="s3">0</span><span class="s1">])</span>
    <span class="s2">if not </span><span class="s1">exe:</span>
        <span class="s2">raise </span><span class="s1">FileNotFoundError(argv[</span><span class="s3">0</span><span class="s1">])</span>
    <span class="s2">return </span><span class="s1">subprocess.Popen([exe, *argv[</span><span class="s3">1</span><span class="s1">:]])</span>
</pre>
</body>
</html>