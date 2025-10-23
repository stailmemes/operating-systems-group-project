<html>
<head>
<title>commands.py</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style type="text/css">
.s0 { color: #d55fde;}
.s1 { color: #bbbbbb;}
.s2 { color: #89ca78;}
.s3 { color: #5c6370;}
.s4 { color: #2bbac5;}
.s5 { color: #d19a66;}
</style>
</head>
<body bgcolor="#282c34">
<table CELLSPACING=0 CELLPADDING=5 COLS=1 WIDTH="100%" BGCOLOR="#606060" >
<tr><td><center>
<font face="Arial, Helvetica" color="#000000">
commands.py</font>
</center></td></tr></table>
<pre><span class="s0">import </span><span class="s1">os</span>
<span class="s0">import </span><span class="s1">shutil</span>
<span class="s0">import </span><span class="s1">sys</span>
<span class="s0">import </span><span class="s1">PrintFormatter</span>
<span class="s0">import </span><span class="s1">subprocess</span>



<span class="s0">def </span><span class="s1">create_file(args):</span>
    <span class="s1">path =args.path</span>
    <span class="s0">with </span><span class="s1">open(path,</span><span class="s2">&quot;w&quot;</span><span class="s1">) </span><span class="s0">as </span><span class="s1">f:</span>
        <span class="s0">pass</span>

<span class="s0">def </span><span class="s1">make_directory(args):</span>
    <span class="s1">path =args.path</span>
    <span class="s0">try</span><span class="s1">:</span>
        <span class="s1">os.mkdir(path)</span>
    <span class="s0">except </span><span class="s1">FileExistsError:</span>
        <span class="s1">PrintFormatter.errorPrint(</span><span class="s2">&quot;dir already exists!&quot;</span><span class="s1">)</span>
    <span class="s0">except </span><span class="s1">FileNotFoundError:</span>
        <span class="s1">PrintFormatter.errorPrint(</span><span class="s2">&quot;parent dir does not exist&quot;</span><span class="s1">)</span>
        <span class="s1">DirCreateInput = PrintFormatter.CInput(</span><span class="s2">&quot;Would you like to make the parent dir? y/n&quot;</span><span class="s1">)</span>
        <span class="s0">if </span><span class="s1">DirCreateInput </span><span class="s0">in </span><span class="s1">(</span><span class="s2">&quot;y&quot;</span><span class="s1">, </span><span class="s2">&quot;yes&quot;</span><span class="s1">, </span><span class="s2">&quot;Y&quot;</span><span class="s1">, </span><span class="s2">&quot;YES&quot;</span><span class="s1">, </span><span class="s2">&quot;Yes&quot;</span><span class="s1">):</span>
            <span class="s0">try</span><span class="s1">:</span>
                <span class="s1">os.makedirs(path)</span>
            <span class="s0">except </span><span class="s1">FileExistsError:</span>
                <span class="s1">PrintFormatter.errorPrint(</span><span class="s2">&quot;Parent dir does exist?&quot;</span><span class="s1">)</span>
        <span class="s0">elif </span><span class="s1">DirCreateInput </span><span class="s0">in </span><span class="s1">(</span><span class="s2">&quot;n&quot;</span><span class="s1">, </span><span class="s2">&quot;no&quot;</span><span class="s1">, </span><span class="s2">&quot;N&quot;</span><span class="s1">, </span><span class="s2">&quot;NO&quot;</span><span class="s1">, </span><span class="s2">&quot;No&quot;</span><span class="s1">):</span>
            <span class="s0">return</span>
        <span class="s0">else</span><span class="s1">:</span>
            <span class="s0">return</span>
    <span class="s0">except </span><span class="s1">PermissionError:</span>
        <span class="s1">PrintFormatter.errorPrint(</span><span class="s2">&quot;Permission denied!&quot;</span><span class="s1">)</span>

<span class="s3"># Lists files in the current directory</span>
<span class="s0">def </span><span class="s1">list_directory(args):</span>
    <span class="s1">files = os.listdir(os.getcwd())</span>
    <span class="s1">PrintFormatter.Blue_Output(os.getcwd() + </span><span class="s2">&quot;  &lt;- current directory&quot;</span><span class="s1">)</span>
    <span class="s0">for </span><span class="s1">file </span><span class="s0">in </span><span class="s1">files:</span>
        <span class="s1">PrintFormatter.Green_Output(file)</span>


<span class="s3"># Change the current directory</span>
<span class="s0">def </span><span class="s1">change_directory(args):</span>
    <span class="s3"># Try to change directory the desired path</span>
    <span class="s0">try</span><span class="s1">:</span>
        <span class="s1">os.chdir(args.path)</span>
        <span class="s1">print(</span><span class="s2">f&quot;Changed directory to </span><span class="s4">{</span><span class="s1">os.getcwd()</span><span class="s4">}</span><span class="s2">&quot;</span><span class="s1">)</span>
    <span class="s3"># Gives an error message if the path does not exist</span>
    <span class="s0">except </span><span class="s1">FileNotFoundError:</span>
        <span class="s1">print(</span><span class="s2">f&quot;Directory </span><span class="s4">{</span><span class="s1">args.path</span><span class="s4">} </span><span class="s2">does not exist&quot;</span><span class="s1">)</span>


<span class="s3"># Exits the shell</span>
<span class="s0">def </span><span class="s1">exit_shell(args):</span>
    <span class="s1">print(</span><span class="s2">&quot;Exiting shell&quot;</span><span class="s1">)</span>
    <span class="s1">sys.exit(</span><span class="s5">0</span><span class="s1">)</span>


<span class="s3"># Prints text to the console</span>
<span class="s0">def </span><span class="s1">echo(args):</span>
    <span class="s1">print(</span><span class="s2">&quot; &quot;</span><span class="s1">.join(args.text))</span>


<span class="s3"># Copies a file</span>
<span class="s0">def </span><span class="s1">copy_file(args):</span>
    <span class="s0">try</span><span class="s1">:</span>
        <span class="s1">shutil.copy(args.source, args.destination)</span>
        <span class="s1">print(</span><span class="s2">f&quot;Copied </span><span class="s4">{</span><span class="s1">args.source</span><span class="s4">} </span><span class="s2">to </span><span class="s4">{</span><span class="s1">args.destination</span><span class="s4">}</span><span class="s2">&quot;</span><span class="s1">)</span>
    <span class="s0">except </span><span class="s1">Exception </span><span class="s0">as </span><span class="s1">e:</span>
        <span class="s1">print(</span><span class="s2">f&quot;Error copying file: </span><span class="s4">{</span><span class="s1">e</span><span class="s4">}</span><span class="s2">&quot;</span><span class="s1">)</span>


<span class="s3"># Moves a file to a desired destination</span>
<span class="s0">def </span><span class="s1">move_file(args):</span>
    <span class="s0">try</span><span class="s1">:</span>
        <span class="s1">shutil.move(args.source, args.destination)</span>
        <span class="s1">print(</span><span class="s2">f&quot;Moved </span><span class="s4">{</span><span class="s1">args.source</span><span class="s4">} </span><span class="s2">to </span><span class="s4">{</span><span class="s1">args.destination</span><span class="s4">}</span><span class="s2">&quot;</span><span class="s1">)</span>
    <span class="s0">except </span><span class="s1">Exception </span><span class="s0">as </span><span class="s1">e:</span>
        <span class="s1">print(</span><span class="s2">f&quot;Error moving file: </span><span class="s4">{</span><span class="s1">e</span><span class="s4">}</span><span class="s2">&quot;</span><span class="s1">)</span>


<span class="s3"># Deletes a file</span>
<span class="s0">def </span><span class="s1">delete_file(args):</span>
    <span class="s0">try</span><span class="s1">:</span>
        <span class="s1">os.remove(args.filename)</span>
        <span class="s1">print(</span><span class="s2">f&quot;Deleted </span><span class="s4">{</span><span class="s1">args.filename</span><span class="s4">}</span><span class="s2">&quot;</span><span class="s1">)</span>
    <span class="s0">except </span><span class="s1">FileNotFoundError:</span>
        <span class="s1">print(</span><span class="s2">f&quot;File </span><span class="s4">{</span><span class="s1">args.filename</span><span class="s4">} </span><span class="s2">does not exist&quot;</span><span class="s1">)</span>
    <span class="s0">except </span><span class="s1">Exception </span><span class="s0">as </span><span class="s1">e:</span>
        <span class="s1">print(</span><span class="s2">f&quot;Error deleting file: </span><span class="s4">{</span><span class="s1">e</span><span class="s4">}</span><span class="s2">&quot;</span><span class="s1">)</span>


<span class="s3"># Run file</span>
<span class="s0">def </span><span class="s1">run_file(args):</span>
    <span class="s1">path = args.path</span>
    <span class="s0">if not </span><span class="s1">os.path.exists(path):</span>
        <span class="s1">PrintFormatter.errorPrint(</span><span class="s2">f&quot;</span><span class="s4">{</span><span class="s1">path</span><span class="s4">}</span><span class="s2">: this file does not exist&quot;</span><span class="s1">)</span>
        <span class="s0">return</span>

    <span class="s1">subprocess.run(args.path + args.args, shell=</span><span class="s0">True</span><span class="s1">)</span>
</pre>
</body>
</html>