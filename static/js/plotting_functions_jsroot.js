

var xhrAlreadyInFligthJSROOT = false;

function plotHistogramJSROOT(divName, url) {

  if(xhrAlreadyInFligthJSROOT) return;
  xhrAlreadyInFligthJSROOT = true;

  getUrl(url, undefined).then(function(response) {
    
    var jsdata = JSON.parse(response); 

    $("#graphdiv").html("");

    histo = JSROOT.JSONR_unref(jsdata.plot);
    JSROOT.draw(divName, histo, "hist");

    xhrAlreadyInFligthJSROOT = false;
  
  });

}