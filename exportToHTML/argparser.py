<html>
<head>
<title>argparser.py</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<style type="text/css">
.s0 { color: #d55fde;}
.s1 { color: #bbbbbb;}
.s2 { color: #89ca78;}
.s3 { color: #5c6370;}
</style>
</head>
<body bgcolor="#282c34">
<table CELLSPACING=0 CELLPADDING=5 COLS=1 WIDTH="100%" BGCOLOR="#606060" >
<tr><td><center>
<font face="Arial, Helvetica" color="#000000">
argparser.py</font>
</center></td></tr></table>
<pre><span class="s0">import </span><span class="s1">argparse</span>
<span class="s0">import </span><span class="s1">commands</span>

<span class="s0">def </span><span class="s1">build_parser():</span>
    <span class="s1">parser = argparse.ArgumentParser(prog=</span><span class="s2">&quot;my-shell&quot;</span><span class="s1">, description=</span><span class="s2">&quot;OS Shell Simulator&quot;</span><span class="s1">)</span>
    <span class="s1">subparsers = parser.add_subparsers(dest=</span><span class="s2">&quot;command&quot;</span><span class="s1">)</span>

    <span class="s3"># list (ls)</span>
    <span class="s1">list_parser = subparsers.add_parser(</span><span class="s2">&quot;ls&quot;</span><span class="s1">, help=</span><span class="s2">&quot;List directory contents&quot;</span><span class="s1">)</span>
    <span class="s1">list_parser.set_defaults(func=commands.list_directory)</span>

    <span class="s3"># cd</span>
    <span class="s1">cd_parser = subparsers.add_parser(</span><span class="s2">&quot;cd&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Change directory&quot;</span><span class="s1">)</span>
    <span class="s1">cd_parser.add_argument(</span><span class="s2">&quot;path&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Path to change to&quot;</span><span class="s1">)</span>
    <span class="s1">cd_parser.set_defaults(func=commands.change_directory)</span>

    <span class="s3"># exit</span>
    <span class="s1">exit_parser = subparsers.add_parser(</span><span class="s2">&quot;exit&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Exit the shell&quot;</span><span class="s1">)</span>
    <span class="s1">exit_parser.set_defaults(func=commands.exit_shell)</span>

    <span class="s3"># echo</span>
    <span class="s1">echo_parser = subparsers.add_parser(</span><span class="s2">&quot;echo&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Print text&quot;</span><span class="s1">)</span>
    <span class="s1">echo_parser.add_argument(</span><span class="s2">&quot;text&quot;</span><span class="s1">, nargs=</span><span class="s2">&quot;+&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Text to print&quot;</span><span class="s1">)</span>
    <span class="s1">echo_parser.set_defaults(func=commands.echo)</span>

    <span class="s3"># cp</span>
    <span class="s1">cp_parser = subparsers.add_parser(</span><span class="s2">&quot;cp&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Copy a file&quot;</span><span class="s1">)</span>
    <span class="s1">cp_parser.add_argument(</span><span class="s2">&quot;source&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Source file&quot;</span><span class="s1">)</span>
    <span class="s1">cp_parser.add_argument(</span><span class="s2">&quot;destination&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Destination file&quot;</span><span class="s1">)</span>
    <span class="s1">cp_parser.set_defaults(func=commands.copy_file)</span>

    <span class="s3"># mv</span>
    <span class="s1">mv_parser = subparsers.add_parser(</span><span class="s2">&quot;mv&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Move a file&quot;</span><span class="s1">)</span>
    <span class="s1">mv_parser.add_argument(</span><span class="s2">&quot;source&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Source file&quot;</span><span class="s1">)</span>
    <span class="s1">mv_parser.add_argument(</span><span class="s2">&quot;destination&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Destination file&quot;</span><span class="s1">)</span>
    <span class="s1">mv_parser.set_defaults(func=commands.move_file)</span>

    <span class="s3"># rm</span>
    <span class="s1">rm_parser = subparsers.add_parser(</span><span class="s2">&quot;rm&quot;</span><span class="s1">, help=</span><span class="s2">&quot;Delete a file&quot;</span><span class="s1">)</span>
    <span class="s1">rm_parser.add_argument(</span><span class="s2">&quot;filename&quot;</span><span class="s1">, help=</span><span class="s2">&quot;File to delete&quot;</span><span class="s1">)</span>
    <span class="s1">rm_parser.set_defaults(func=commands.delete_file)</span>

    <span class="s3"># run</span>
    <span class="s1">run_parser = subparsers.add_parser(</span><span class="s2">&quot;run&quot;</span><span class="s1">, help=</span><span class="s2">&quot;executes files and programs&quot;</span><span class="s1">)</span>
    <span class="s1">run_parser.add_argument(</span><span class="s2">&quot;path&quot;</span><span class="s1">, help = </span><span class="s2">&quot;path to file&quot;</span><span class="s1">)</span>
    <span class="s1">run_parser.set_defaults(func=commands.run_file)</span>

    <span class="s3">#make dir</span>
    <span class="s1">mkdir_parser = subparsers.add_parser(</span><span class="s2">&quot;mkdir&quot;</span><span class="s1">, help = </span><span class="s2">&quot;makes a directory &quot;</span><span class="s1">)</span>
    <span class="s1">mkdir_parser.add_argument(</span><span class="s2">&quot;path&quot;</span><span class="s1">, help = </span><span class="s2">&quot;path to place to create dir&quot;</span><span class="s1">)</span>
    <span class="s1">mkdir_parser.set_defaults(func= commands.make_directory)</span>

    <span class="s3">#create file</span>
    <span class="s1">crf_parser = subparsers.add_parser(</span><span class="s2">&quot;crf&quot;</span><span class="s1">, help = </span><span class="s2">&quot;makes an empty file&quot;</span><span class="s1">)</span>
    <span class="s1">crf_parser.add_argument(</span><span class="s2">&quot;path&quot;</span><span class="s1">, help= </span><span class="s2">&quot;path where file is created&quot;</span><span class="s1">)</span>
    <span class="s1">crf_parser.set_defaults(func=commands.create_file)</span>


    <span class="s0">return </span><span class="s1">parser</span>
</pre>
</body>
</html>